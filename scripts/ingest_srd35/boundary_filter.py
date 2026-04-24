from __future__ import annotations

import re

from .sectioning import sanitize_identifier

MIN_SUSPICIOUS_SECTION_CHARS = 60
MIN_KEEP_TABLE_SECTION_PARAGRAPHS = 1
TRUNCATED_TITLE_SUFFIXES = {"and", "or", "the", "of", "to", "for", "a", "an"}


# Boilerplate phrases now come from the per-source manifest at call time.
# Stat-field-lookalike detection: vocabulary-free formatting check using the
# section's title block formatting (starts_with_bold + short Word: shape).
# Catches the case where the heading-candidate sectioner promoted a bold
# stat-field line to a section title in files where the entry annotator
# didn't fire.
_FIELD_LIKE_TITLE_RE = re.compile(r"^[A-Z][\w '/-]+:\s*\S?")


def _looks_stat_field_lookalike(candidate: dict) -> bool:
    """Return True when a candidate title looks like a bold-prefixed stat
    block field that the heading-candidate path mistakenly promoted to a
    section title (e.g., \"Components: V, S, M\").

    This is the formatting-driven replacement for the deleted vocabulary
    list `_SPELL_BLOCK_FIELDS`. Only fires when the title block is bold
    AND short AND matches the generic Word:value pattern — works across
    editions/sources because it relies on the encoding shape, not specific
    field names.
    """
    if not candidate.get("title_starts_with_bold", False):
        return False
    title = candidate["section_title"].strip()
    if len(title) > 80:
        return False
    return bool(_FIELD_LIKE_TITLE_RE.match(title))


def _looks_truncated_title(title: str) -> bool:
    original_tokens = re.findall(r"[A-Za-z]+", title)
    if not original_tokens:
        return True
    if len(original_tokens) == 1:
        token = original_tokens[0]
        if token.isupper():
            return False
        if len(token) <= 4:
            return True
    lower_last = original_tokens[-1].lower()
    if lower_last in TRUNCATED_TITLE_SUFFIXES:
        return True
    return False


def _looks_table_label_title(title: str) -> bool:
    """Return True when a candidate title is a table-label heading.

    Two patterns:
    - Pipe-row syntax: title contains "|" (inline table header or cell row)
    - Named table: title starts with "Table:" (RTF Table: Name heading style)
    """
    return "|" in title or title.strip().lower().startswith("table:")


def _is_boilerplate_stub(
    candidate: dict,
    file_stem: str,
    source_file_name: str,
    boilerplate_phrases: set[str],
) -> bool:
    if source_file_name.lower() == "legal.rtf":
        return False
    content = candidate["content"].lower()
    if candidate["body_char_count"] > 220:
        return False
    has_phrase = any(phrase in content for phrase in boilerplate_phrases)
    if sanitize_identifier(candidate["section_title"]) == sanitize_identifier(file_stem):
        return has_phrase or candidate["body_char_count"] < 40
    return has_phrase


def _is_table_fragment(candidate: dict) -> bool:
    counts = candidate.get("block_type_counts", {})
    table_rows = counts.get("table_row", 0)
    paragraphs = counts.get("paragraph", 0)
    if table_rows == 0:
        return False
    return paragraphs < MIN_KEEP_TABLE_SECTION_PARAGRAPHS or candidate["body_char_count"] < 200


def _merge_section(target: dict, incoming: dict) -> None:
    target["content"] = f"{target['content']}\n\n{incoming['content']}".strip()
    target["body_char_count"] = len(target["content"])
    target["block_end_index"] = incoming["block_end_index"]
    target["block_end_id"] = incoming["block_end_id"]
    for key, value in incoming.get("block_type_counts", {}).items():
        target["block_type_counts"][key] = target["block_type_counts"].get(key, 0) + value


def _prepend_section(target: dict, incoming: dict) -> None:
    target["content"] = f"{incoming['content']}\n\n{target['content']}".strip()
    target["body_char_count"] = len(target["content"])
    target["block_start_index"] = incoming["block_start_index"]
    target["block_start_id"] = incoming["block_start_id"]
    for key, value in incoming.get("block_type_counts", {}).items():
        target["block_type_counts"][key] = target["block_type_counts"].get(key, 0) + value


def apply_boundary_filters(
    file_stem: str,
    source_file_name: str,
    candidates: list[dict],
    *,
    boilerplate_phrases: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    boilerplate_phrases = boilerplate_phrases or set()

    if source_file_name.lower() == "legal.rtf":
        return (
            [dict(candidate) for candidate in candidates],
            [
                {
                    "candidate_index": index + 1,
                    "title": candidate["section_title"].strip(),
                    "action": "accepted",
                    "reason_code": "legal_source_passthrough",
                    "body_char_count": candidate["body_char_count"],
                    "block_start_id": candidate.get("block_start_id"),
                    "block_end_id": candidate.get("block_end_id"),
                }
                for index, candidate in enumerate(candidates)
            ],
        )

    accepted: list[dict] = []
    decisions: list[dict] = []
    forward_merge_bucket: dict | None = None

    for index, candidate in enumerate(candidates):
        title = candidate["section_title"].strip()

        # Entry-annotated sections accepted unconditionally.
        if "entry_metadata" in candidate:
            materialized = dict(candidate)
            materialized["block_type_counts"] = dict(candidate.get("block_type_counts", {}))
            if forward_merge_bucket is not None:
                _prepend_section(materialized, forward_merge_bucket)
                forward_merge_bucket = None
            accepted.append(materialized)
            decisions.append(
                {
                    "candidate_index": index + 1,
                    "title": title,
                    "action": "accepted",
                    "reason_code": "entry_annotated",
                    "body_char_count": candidate["body_char_count"],
                    "block_start_id": candidate.get("block_start_id"),
                    "block_end_id": candidate.get("block_end_id"),
                }
            )
            continue

        reason_code = "accepted_clean"
        action = "accepted"

        if index == 0 and _is_boilerplate_stub(candidate, file_stem, source_file_name, boilerplate_phrases):
            action = "merged_forward" if len(candidates) > 1 else "dropped"
            reason_code = "boilerplate_opener_stub"
        elif _looks_table_label_title(title):
            action = "merged_backward" if accepted else "merged_forward"
            reason_code = "table_label_title"
        elif _looks_stat_field_lookalike(candidate):
            action = "merged_backward" if accepted else "merged_forward"
            reason_code = "stat_field_lookalike"
        elif _is_table_fragment(candidate):
            action = "merged_backward" if accepted else "merged_forward"
            reason_code = "table_fragment_section"
        elif candidate["body_char_count"] < MIN_SUSPICIOUS_SECTION_CHARS or _looks_truncated_title(title):
            action = "merged_backward" if accepted else "merged_forward"
            reason_code = "suspicious_short_or_truncated"

        if action == "accepted":
            materialized = dict(candidate)
            materialized["block_type_counts"] = dict(candidate.get("block_type_counts", {}))
            if forward_merge_bucket is not None:
                _prepend_section(materialized, forward_merge_bucket)
                forward_merge_bucket = None
            accepted.append(materialized)
        elif action == "merged_backward":
            if accepted:
                _merge_section(accepted[-1], candidate)
            elif len(candidates) > 1:
                action = "merged_forward"
                reason_code = f"{reason_code}_fallback_forward"
                if forward_merge_bucket is None:
                    forward_merge_bucket = dict(candidate)
                else:
                    _merge_section(forward_merge_bucket, candidate)
            else:
                action = "dropped"
                reason_code = f"{reason_code}_fallback_drop"
        elif action == "merged_forward":
            if forward_merge_bucket is None:
                forward_merge_bucket = dict(candidate)
            else:
                _merge_section(forward_merge_bucket, candidate)

        decisions.append(
            {
                "candidate_index": index + 1,
                "title": title,
                "action": action,
                "reason_code": reason_code,
                "body_char_count": candidate["body_char_count"],
                "block_start_id": candidate.get("block_start_id"),
                "block_end_id": candidate.get("block_end_id"),
            }
        )

    if forward_merge_bucket is not None:
        if accepted:
            _merge_section(accepted[-1], forward_merge_bucket)
            decisions.append(
                {
                    "candidate_index": len(candidates) + 1,
                    "title": forward_merge_bucket["section_title"],
                    "action": "merged_backward",
                    "reason_code": "forward_bucket_flush_to_last",
                    "body_char_count": forward_merge_bucket["body_char_count"],
                    "block_start_id": forward_merge_bucket.get("block_start_id"),
                    "block_end_id": forward_merge_bucket.get("block_end_id"),
                }
            )
        else:
            accepted.append(forward_merge_bucket)
            decisions.append(
                {
                    "candidate_index": len(candidates) + 1,
                    "title": forward_merge_bucket["section_title"],
                    "action": "accepted",
                    "reason_code": "forward_bucket_promoted_fallback",
                    "body_char_count": forward_merge_bucket["body_char_count"],
                    "block_start_id": forward_merge_bucket.get("block_start_id"),
                    "block_end_id": forward_merge_bucket.get("block_end_id"),
                }
            )

    return accepted, decisions
