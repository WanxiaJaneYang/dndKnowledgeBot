"""Answer composer: builds 1-3 segments per §3.3 of the minimal-answer-path design.

Emits a primary segment (the top evidence item) plus up to two supporting
segments drawn from siblings in the same ``(document_id, section_root)`` group
and a distinct-signal cross-section fallback. All segment text is a chunk
excerpt; the composer never synthesizes prose.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal

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
    primary = pack.evidence[0]
    segments: list[_ComposedSegment] = [
        _build_segment("seg_1", primary, role="primary"),
    ]

    siblings = list(_iter_siblings(pack, primary))
    used_sibling_ids: set[str] = set()

    # Slot 1: first sibling in rank order.
    if siblings:
        slot1 = siblings[0]
        used_sibling_ids.add(slot1.chunk_id)
        segments.append(_build_segment("seg_2", slot1, role="sibling"))

    # Slot 2: distinct-signal cross-section, else fallback sibling.
    slot2_item, slot2_role = _select_slot2(pack, primary, siblings, used_sibling_ids)
    if slot2_item is not None:
        segment_id = f"seg_{len(segments) + 1}"
        segments.append(_build_segment(segment_id, slot2_item, role=slot2_role))

    return tuple(segments)


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


def _select_slot2(
    pack: EvidencePack,
    primary: EvidenceItem,
    siblings: list[EvidenceItem],
    used_sibling_ids: set[str],
) -> tuple[EvidenceItem | None, Literal["sibling", "cross-section"]]:
    """Pick the slot-2 item: distinct-signal cross-section, else fallback sibling."""
    cross_section = _find_cross_section(pack, primary)
    if cross_section is not None:
        return cross_section, "cross-section"

    for sibling in siblings:
        if sibling.chunk_id not in used_sibling_ids:
            return sibling, "sibling"

    return None, "sibling"


def _find_cross_section(pack: EvidencePack, primary: EvidenceItem) -> EvidenceItem | None:
    """Return the lowest-rank cross-section item whose hit set is NOT a subset of primary's.

    Distinctness comparison is limited to ``exact_phrase_hits`` and
    ``protected_phrase_hits`` only (spec §3.3); ``section_path_hit`` is
    excluded because the section-root grouping already handles it.
    """
    primary_hits = _phrase_hit_set(primary)
    best: EvidenceItem | None = None
    for item in pack.evidence:
        if item.chunk_id == primary.chunk_id:
            continue
        if item.section_root == primary.section_root:
            continue
        candidate_hits = _phrase_hit_set(item)
        if candidate_hits.issubset(primary_hits):
            continue
        if best is None or item.rank < best.rank:
            best = item
    return best


def _phrase_hit_set(item: EvidenceItem) -> set[str]:
    signals = item.match_signals
    return set(signals["exact_phrase_hits"]) | set(signals["protected_phrase_hits"])
