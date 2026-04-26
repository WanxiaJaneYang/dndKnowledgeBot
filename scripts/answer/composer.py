"""Answer composer: builds 1-3 segments per section 3.3 of the minimal-answer-path design.

Emits a primary segment (the top evidence item) plus up to two supporting
segments drawn from siblings in the same ``(document_id, section_root)`` group
and a distinct-signal cross-section fallback. All segment text is a chunk
excerpt; the composer never synthesizes prose.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal

from scripts.answer.contracts import SlotDecision
from scripts.retrieval.evidence_pack import EvidenceItem, EvidencePack


_EXCERPT_MAX_LEN = 500


@dataclass(frozen=True)
class _ComposedSegment:
    """Internal composer output carrying enough context for the binder and CLI."""

    segment_id: str
    text: str
    support_type: Literal["direct_support", "supported_inference"]
    evidence_item: EvidenceItem
    role: Literal["primary", "sibling", "cross-section"]


def compose_segments(pack: EvidencePack) -> tuple[_ComposedSegment, ...]:
    """Compose 1-3 excerpt-based segments from the pack's evidence."""
    segments, _ = compose_segments_with_decisions(pack)
    return segments


def compose_segments_with_decisions(
    pack: EvidencePack,
) -> tuple[tuple[_ComposedSegment, ...], tuple[SlotDecision, ...]]:
    """Compose segments and record why each slot was filled or left empty."""
    primary = pack.evidence[0]
    segments: list[_ComposedSegment] = [
        _build_segment("seg_1", primary, role="primary"),
    ]
    decisions: list[SlotDecision] = [
        SlotDecision(
            slot="primary",
            chosen_role="primary",
            outcome="filled",
            chosen_chunk_id=primary.chunk_id,
            rejected=(),
            reason="top_ranked_evidence_item",
        )
    ]

    siblings = list(_iter_siblings(pack, primary))
    used_sibling_ids: set[str] = set()

    if siblings:
        slot1 = siblings[0]
        used_sibling_ids.add(slot1.chunk_id)
        segments.append(_build_segment("seg_2", slot1, role="sibling"))
        decisions.append(
            SlotDecision(
                slot="sibling",
                chosen_role="sibling",
                outcome="filled",
                chosen_chunk_id=slot1.chunk_id,
                rejected=(),
                reason="first_ranked_sibling",
            )
        )
    else:
        decisions.append(
            SlotDecision(
                slot="sibling",
                chosen_role=None,
                outcome="skipped",
                chosen_chunk_id=None,
                rejected=(),
                reason="no_sibling_available",
            )
        )

    cross_section, cross_rejections = _find_cross_section_with_rejections(pack, primary)
    if cross_section is not None:
        segment_id = f"seg_{len(segments) + 1}"
        segments.append(_build_segment(segment_id, cross_section, role="cross-section"))
        decisions.append(
            SlotDecision(
                slot="cross-section",
                chosen_role="cross-section",
                outcome="filled",
                chosen_chunk_id=cross_section.chunk_id,
                rejected=tuple(cross_rejections),
                reason="distinct_cross_section_found",
            )
        )
        return tuple(segments), tuple(decisions)

    decisions.append(
        SlotDecision(
            slot="cross-section",
            chosen_role=None,
            outcome="skipped",
            chosen_chunk_id=None,
            rejected=tuple(cross_rejections),
            reason="no_distinct_cross_section",
        )
    )

    fallback_sibling, fallback_rejections = _find_fallback_sibling(siblings, used_sibling_ids)
    if fallback_sibling is not None:
        segment_id = f"seg_{len(segments) + 1}"
        segments.append(_build_segment(segment_id, fallback_sibling, role="sibling"))
        decisions.append(
            SlotDecision(
                slot="fallback-sibling",
                chosen_role="sibling",
                outcome="filled",
                chosen_chunk_id=fallback_sibling.chunk_id,
                rejected=tuple(fallback_rejections),
                reason="fallback_sibling_found",
            )
        )
    else:
        decisions.append(
            SlotDecision(
                slot="fallback-sibling",
                chosen_role=None,
                outcome="skipped",
                chosen_chunk_id=None,
                rejected=tuple(fallback_rejections),
                reason="no_fallback_sibling_available",
            )
        )

    return tuple(segments), tuple(decisions)


def _build_segment(
    segment_id: str,
    item: EvidenceItem,
    *,
    role: Literal["primary", "sibling", "cross-section"],
) -> _ComposedSegment:
    return _ComposedSegment(
        segment_id=segment_id,
        text=_truncate(item.content),
        support_type=_classify_support(item),
        evidence_item=item,
        role=role,
    )


def _truncate(content: str) -> str:
    if len(content) <= _EXCERPT_MAX_LEN:
        return content
    return content[:_EXCERPT_MAX_LEN].rstrip() + "…"


def _classify_support(item: EvidenceItem) -> Literal["direct_support", "supported_inference"]:
    signals = item.match_signals
    if signals["exact_phrase_hits"] or signals["protected_phrase_hits"]:
        return "direct_support"
    return "supported_inference"


def _iter_siblings(pack: EvidencePack, primary: EvidenceItem) -> Iterator[EvidenceItem]:
    """Yield siblings (same document_id + section_root) excluding the primary, by rank."""
    for item in pack.evidence:
        if item.chunk_id == primary.chunk_id:
            continue
        if item.document_id == primary.document_id and item.section_root == primary.section_root:
            yield item


def _find_cross_section_with_rejections(
    pack: EvidencePack,
    primary: EvidenceItem,
) -> tuple[EvidenceItem | None, list[tuple[str, str, str]]]:
    """Return the best distinct cross-section item plus rejected candidates."""
    primary_hits = _phrase_hit_set(primary)
    best: EvidenceItem | None = None
    rejected: list[tuple[str, str, str]] = []
    for item in pack.evidence:
        if item.chunk_id == primary.chunk_id:
            continue
        if item.document_id == primary.document_id and item.section_root == primary.section_root:
            rejected.append((item.chunk_id, "same_group_as_primary", "same_group_as_primary"))
            continue
        candidate_hits = _phrase_hit_set(item)
        if candidate_hits.issubset(primary_hits):
            rejected.append(
                (item.chunk_id, "hit_set_subset_of_primary", "subset_of_primary")
            )
            continue
        if best is None or item.rank < best.rank:
            best = item
    return best, rejected


def _find_fallback_sibling(
    siblings: list[EvidenceItem],
    used_sibling_ids: set[str],
) -> tuple[EvidenceItem | None, list[tuple[str, str, str]]]:
    rejected: list[tuple[str, str, str]] = []
    for sibling in siblings:
        if sibling.chunk_id in used_sibling_ids:
            rejected.append(
                (
                    sibling.chunk_id,
                    "already_used_in_earlier_slot",
                    "used_by_slot_1",
                )
            )
            continue
        return sibling, rejected
    return None, rejected


def _phrase_hit_set(item: EvidenceItem) -> set[str]:
    signals = item.match_signals
    return set(signals["exact_phrase_hits"]) | set(signals["protected_phrase_hits"])
