"""Tests for the answer composer (§3.3)."""
from __future__ import annotations

from scripts.answer.composer import compose_segments
from scripts.retrieval.contracts import MatchSignals, NormalizedQuery
from scripts.retrieval.evidence_pack import (
    EvidenceItem,
    EvidencePack,
    PipelineTrace,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_query() -> NormalizedQuery:
    return NormalizedQuery(
        raw_query="q",
        normalized_text="q",
        tokens=["q"],
        protected_phrases=[],
        aliases_applied=[],
    )


def _make_signals(
    *,
    exact: list[str] | None = None,
    protected: list[str] | None = None,
    section_path_hit: bool = False,
    token_overlap_count: int = 0,
) -> MatchSignals:
    return {
        "exact_phrase_hits": list(exact or []),
        "protected_phrase_hits": list(protected or []),
        "section_path_hit": section_path_hit,
        "token_overlap_count": token_overlap_count,
    }


def _make_item(
    chunk_id: str,
    *,
    rank: int,
    document_id: str = "doc::main",
    section_root: str = "Combat",
    content: str = "Rule text.",
    signals: MatchSignals | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        chunk_id=chunk_id,
        document_id=document_id,
        rank=rank,
        content=content,
        chunk_type="rule_section",
        source_ref={
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        locator={"section_path": [section_root], "source_location": "test"},
        match_signals=signals or _make_signals(exact=["q"]),
        section_root=section_root,
    )


def _make_pack(items: list[EvidenceItem]) -> EvidencePack:
    return EvidencePack(
        query=_make_query(),
        constraints_summary={},
        evidence=tuple(items),
        trace=PipelineTrace(
            total_candidates=len(items),
            group_count=0,
            group_summaries=(),
        ),
    )


# ---------------------------------------------------------------------------
# Tests — segment count & support type
# ---------------------------------------------------------------------------


def test_single_evidence_produces_primary_only():
    primary = _make_item("c1", rank=1)
    segments = compose_segments(_make_pack([primary]))
    assert len(segments) == 1
    assert segments[0].role == "primary"
    assert segments[0].segment_id == "seg_1"


def test_primary_with_exact_phrase_is_direct_support():
    primary = _make_item("c1", rank=1, signals=_make_signals(exact=["foo"]))
    segments = compose_segments(_make_pack([primary]))
    assert segments[0].support_type == "direct_support"


def test_primary_with_only_section_path_hit_is_supported_inference():
    primary = _make_item("c1", rank=1, signals=_make_signals(section_path_hit=True))
    segments = compose_segments(_make_pack([primary]))
    assert segments[0].support_type == "supported_inference"


def test_primary_with_two_siblings_yields_three_segments_same_group():
    primary = _make_item("c1", rank=1)
    sib1 = _make_item("c2", rank=2)
    sib2 = _make_item("c3", rank=3)
    segments = compose_segments(_make_pack([primary, sib1, sib2]))
    assert len(segments) == 3
    assert segments[1].role == "sibling"
    assert segments[2].role == "sibling"
    keys = {
        (s.evidence_item.document_id, s.evidence_item.section_root) for s in segments
    }
    assert len(keys) == 1


def test_sibling_plus_distinct_cross_section_fills_slot2():
    primary = _make_item(
        "c1", rank=1, signals=_make_signals(exact=["A"])
    )
    sib = _make_item("c2", rank=2)
    cross = _make_item(
        "c3",
        rank=3,
        document_id="doc::other",
        section_root="Spells",
        signals=_make_signals(exact=["B"]),
    )
    segments = compose_segments(_make_pack([primary, sib, cross]))
    assert len(segments) == 3
    assert segments[2].role == "cross-section"
    assert segments[2].evidence_item.section_root != primary.section_root


def test_cross_section_subset_falls_back_to_second_sibling():
    primary = _make_item(
        "c1", rank=1, signals=_make_signals(exact=["A", "B"])
    )
    sib1 = _make_item("c2", rank=2)
    cross = _make_item(
        "c3",
        rank=3,
        document_id="doc::other",
        section_root="Spells",
        signals=_make_signals(exact=["A"]),
    )
    sib2 = _make_item("c4", rank=4)
    segments = compose_segments(_make_pack([primary, sib1, cross, sib2]))
    assert len(segments) == 3
    assert segments[1].evidence_item.chunk_id == "c2"
    assert segments[2].role == "sibling"
    assert segments[2].evidence_item.chunk_id == "c4"


def test_cross_section_subset_no_second_sibling_leaves_slot2_empty():
    primary = _make_item(
        "c1", rank=1, signals=_make_signals(exact=["A", "B"])
    )
    sib = _make_item("c2", rank=2)
    cross = _make_item(
        "c3",
        rank=3,
        document_id="doc::other",
        section_root="Spells",
        signals=_make_signals(exact=["A"]),
    )
    segments = compose_segments(_make_pack([primary, sib, cross]))
    assert len(segments) == 2
    assert segments[1].role == "sibling"


def test_primary_plus_cross_section_without_siblings():
    primary = _make_item("c1", rank=1, signals=_make_signals(exact=["A"]))
    cross = _make_item(
        "c2",
        rank=2,
        document_id="doc::other",
        section_root="Spells",
        signals=_make_signals(exact=["B"]),
    )
    segments = compose_segments(_make_pack([primary, cross]))
    assert len(segments) == 2
    assert segments[1].role == "cross-section"
    assert segments[1].evidence_item.chunk_id == "c2"


def test_cross_section_lowest_rank_wins():
    primary = _make_item("c1", rank=1, signals=_make_signals(exact=["A"]))
    cross_far = _make_item(
        "c2",
        rank=5,
        document_id="doc::other",
        section_root="Spells",
        signals=_make_signals(exact=["B"]),
    )
    cross_near = _make_item(
        "c3",
        rank=3,
        document_id="doc::other",
        section_root="Spells",
        signals=_make_signals(exact=["C"]),
    )
    segments = compose_segments(_make_pack([primary, cross_near, cross_far]))
    assert len(segments) == 2
    assert segments[1].evidence_item.chunk_id == "c3"


def test_empty_primary_hitset_accepts_any_cross_section_with_phrase_hits():
    """Per §3.3 edge case — empty primary hit set trivially has no subset match."""
    primary = _make_item(
        "c1", rank=1, signals=_make_signals(section_path_hit=True)
    )
    cross = _make_item(
        "c2",
        rank=2,
        document_id="doc::other",
        section_root="Spells",
        signals=_make_signals(exact=["X"]),
    )
    segments = compose_segments(_make_pack([primary, cross]))
    assert len(segments) == 2
    assert segments[1].role == "cross-section"


# ---------------------------------------------------------------------------
# Tests — excerpt truncation
# ---------------------------------------------------------------------------


def test_content_501_chars_truncated():
    content = "x" * 501
    primary = _make_item("c1", rank=1, content=content)
    segments = compose_segments(_make_pack([primary]))
    text = segments[0].text
    assert text.endswith("…")
    # 500 chars + the ellipsis character
    assert len(text) == 501


def test_content_500_chars_not_truncated():
    content = "x" * 500
    primary = _make_item("c1", rank=1, content=content)
    segments = compose_segments(_make_pack([primary]))
    assert segments[0].text == content


def test_content_100_chars_not_truncated():
    content = "x" * 100
    primary = _make_item("c1", rank=1, content=content)
    segments = compose_segments(_make_pack([primary]))
    assert segments[0].text == content
