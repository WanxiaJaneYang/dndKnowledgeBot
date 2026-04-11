from __future__ import annotations

import re

from .sectioning import sanitize_identifier

MIN_SUSPICIOUS_SECTION_CHARS = 60
MIN_KEEP_TABLE_SECTION_PARAGRAPHS = 1
BOILERPLATE_PHRASES = {
    "visit",
    "www.wizards.com",
    "system reference document",
    "contains all of the",
}
TRUNCATED_TITLE_SUFFIXES = {"and", "or", "the", "of", "to", "for", "a", "an"}


def _looks_truncated_title(title: str) -> bool:
    tokens = re.findall(r"[a-z]+", title.lower())
    if not tokens:
        return True
    if len(tokens) == 1 and len(tokens[0]) <= 4:
        return True
    if tokens[-1] in TRUNCATED_TITLE_SUFFIXES:
        return True
    return False


def _looks_table_label_title(title: str) -> bool:
    return "|" in title


def _is_boilerplate_stub(candidate: dict, file_stem: str, source_file_name: str) -> bool:
    if source_file_name.lower() == "legal.rtf":
        return False
    content = candidate["content"].lower()
    if candidate["body_char_count"] > 220:
        return False
    has_phrase = any(phrase in content for phrase in BOILERPLATE_PHRASES)
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


def apply_boundary_filters(file_stem: str, source_file_name: str, candidates: list[dict]) -> tuple[list[dict], list[dict]]:
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
        reason_code = "accepted_clean"
        action = "accepted"

        if index == 0 and _is_boilerplate_stub(candidate, file_stem, source_file_name):
            action = "merged_forward" if len(candidates) > 1 else "dropped"
            reason_code = "boilerplate_opener_stub"
        elif _looks_table_label_title(title):
            action = "merged_backward" if accepted else "merged_forward"
            reason_code = "table_label_title"
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
