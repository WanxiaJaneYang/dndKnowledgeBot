"""Tests for the citation binder (§3.4)."""
from __future__ import annotations

from scripts.answer.citation_binder import bind_citations
from scripts.answer.composer import _ComposedSegment
from scripts.retrieval.contracts import MatchSignals, NormalizedQuery
from scripts.retrieval.evidence_pack import (
    EvidenceItem,
    EvidencePack,
    PipelineTrace,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_SOURCE_REF = {
    "source_id": "srd_35",
    "title": "System Reference Document",
    "edition": "3.5e",
    "source_type": "srd",
    "authority_level": "official_reference",
}


def _make_query() -> NormalizedQuery:
    return NormalizedQuery(
        raw_query="q",
        normalized_text="q",
        tokens=["q"],
        protected_phrases=[],
        aliases_applied=[],
    )


def _empty_signals() -> MatchSignals:
    return {
        "exact_phrase_hits": [],
        "protected_phrase_hits": [],
        "section_path_hit": True,
        "token_overlap_count": 0,
    }


def _make_item(
    chunk_id: str,
    *,
    content: str,
    rank: int = 1,
    locator: dict | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        chunk_id=chunk_id,
        document_id="doc::main",
        rank=rank,
        content=content,
        chunk_type="rule_section",
        source_ref=_SOURCE_REF,
        locator=locator or {"section_path": ["Combat"], "source_location": "test"},
        match_signals=_empty_signals(),
        section_root="Combat",
        chunk_ids=(chunk_id,),
        start_chunk_id=chunk_id,
        end_chunk_id=chunk_id,
        merge_reason="singleton",
        parent_chunk_id=None,
        previous_chunk_id=None,
        next_chunk_id=None,
    )


def _make_composed(
    segment_id: str,
    item: EvidenceItem,
    *,
    text: str | None = None,
    role: str = "primary",
) -> _ComposedSegment:
    return _ComposedSegment(
        segment_id=segment_id,
        text=text if text is not None else item.content,
        support_type="direct_support",
        evidence_item=item,
        role=role,  # type: ignore[arg-type]
    )


def _make_pack() -> EvidencePack:
    return EvidencePack(
        query=_make_query(),
        constraints_summary={},
        evidence=(),
        trace=PipelineTrace(total_candidates=0, group_count=0, group_summaries=()),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_single_segment_single_citation():
    item = _make_item("chunk::a", content="alpha")
    composed = (_make_composed("seg_1", item),)
    segments, citations = bind_citations(composed, _make_pack())

    assert len(segments) == 1
    assert len(citations) == 1
    assert citations[0].citation_id == "cit_1"
    assert segments[0].citation_ids == ("cit_1",)


def test_three_segments_different_chunks_three_citations():
    items = [_make_item(f"chunk::{i}", content=f"text-{i}") for i in range(3)]
    composed = tuple(
        _make_composed(f"seg_{i + 1}", item) for i, item in enumerate(items)
    )
    segments, citations = bind_citations(composed, _make_pack())

    assert [c.citation_id for c in citations] == ["cit_1", "cit_2", "cit_3"]
    assert [s.citation_ids for s in segments] == [
        ("cit_1",),
        ("cit_2",),
        ("cit_3",),
    ]


def test_duplicate_chunk_and_excerpt_shares_citation():
    item = _make_item("chunk::shared", content="same text")
    composed = (
        _make_composed("seg_1", item),
        _make_composed("seg_2", item),
    )
    segments, citations = bind_citations(composed, _make_pack())

    assert len(citations) == 1
    assert citations[0].citation_id == "cit_1"
    assert segments[0].citation_ids == ("cit_1",)
    assert segments[1].citation_ids == ("cit_1",)


def test_citation_excerpt_equals_segment_text():
    item = _make_item("chunk::a", content="full content")
    composed = (_make_composed("seg_1", item, text="excerpt text"),)
    _, citations = bind_citations(composed, _make_pack())
    assert citations[0].excerpt == "excerpt text"


def test_citation_carries_source_ref_and_locator():
    locator = {"section_path": ["Magic"], "source_location": "Spells.rtf#42"}
    item = _make_item("chunk::z", content="c", locator=locator)
    composed = (_make_composed("seg_1", item),)
    _, citations = bind_citations(composed, _make_pack())
    assert citations[0].source_ref == _SOURCE_REF
    assert citations[0].locator == locator
