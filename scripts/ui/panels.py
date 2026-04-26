from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def format_answer_segments(segments: Sequence[object]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for segment in segments:
        citation_ids = tuple(_read(segment, "citation_ids"))
        rows.append(
            {
                "segment_id": _read(segment, "segment_id"),
                "support_type": _read(segment, "support_type"),
                "citations": " ".join(f"[{citation_id}]" for citation_id in citation_ids),
                "text": _read(segment, "text"),
            }
        )
    return rows


def format_slot_decision_rows(decisions: Sequence[object]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for decision in decisions:
        rejected = _read(decision, "rejected")
        rejected_text = "; ".join(
            f"{chunk_id}:{reason_code}" for chunk_id, reason_code, _detail in rejected
        )
        rows.append(
            {
                "slot": _read(decision, "slot"),
                "outcome": _read(decision, "outcome"),
                "chosen_role": _read(decision, "chosen_role"),
                "chosen_chunk_id": _read(decision, "chosen_chunk_id"),
                "reason": _read(decision, "reason"),
                "rejected": rejected_text,
            }
        )
    return rows


def format_candidate_rows(items: Sequence[object]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        signals = _read(item, "match_signals")
        rows.append(
            {
                "rank": _read(item, "rank"),
                "chunk_id": _read(item, "chunk_id"),
                "document_id": _read(item, "document_id"),
                "section_root": _candidate_section_root(item),
                "chunk_type": _read(item, "chunk_type"),
                "match_signals": _format_match_signals(signals),
            }
        )
    return rows


def format_citation_rows(citations: Sequence[object]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for citation in citations:
        source_ref = _read(citation, "source_ref")
        locator = _read(citation, "locator")
        rows.append(
            {
                "citation_id": _read(citation, "citation_id"),
                "chunk_id": _read(citation, "chunk_id"),
                "title": source_ref.get("title", "?"),
                "locator": _format_locator(locator),
                "excerpt": _read(citation, "excerpt"),
            }
        )
    return rows


def _format_match_signals(signals: Mapping[str, Any]) -> str:
    parts: list[str] = []
    if signals.get("exact_phrase_hits"):
        parts.append(f"exact={signals['exact_phrase_hits']}")
    if signals.get("protected_phrase_hits"):
        parts.append(f"protected={signals['protected_phrase_hits']}")
    if signals.get("section_path_hit"):
        parts.append("section_path_hit")
    if signals.get("token_overlap_count"):
        parts.append(f"token_overlap={signals['token_overlap_count']}")
    return "; ".join(parts) if parts else "(none)"


def _format_locator(locator: Mapping[str, Any]) -> str:
    parts: list[str] = []
    if section_path := locator.get("section_path"):
        parts.append(" > ".join(section_path))
    if source_location := locator.get("source_location"):
        parts.append(source_location)
    return " | ".join(parts) if parts else str(locator)


def _candidate_section_root(item: object) -> str | None:
    if isinstance(item, Mapping):
        section_root = item.get("section_root")
        if section_root is not None:
            return section_root
        locator = item.get("locator", {})
    else:
        section_root = getattr(item, "section_root", None)
        if section_root is not None:
            return section_root
        locator = getattr(item, "locator")

    section_path = locator.get("section_path", ())
    if section_path:
        return section_path[0]
    return None


def _read(value: object, field: str) -> Any:
    if isinstance(value, Mapping):
        return value[field]
    return getattr(value, field)
