"""Tests for adjacent-chunk consolidation (issue #34 remaining scope)."""
from __future__ import annotations

from scripts.retrieval.candidate_consolidation import (
    EvidenceSpan,
    SpanGroup,
    consolidate_adjacent,
)
from scripts.retrieval.candidate_shaping import CandidateGroup
from scripts.retrieval.contracts import LexicalCandidate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_candidate(
    chunk_id: str,
    rank: int,
    *,
    document_id: str = "doc::combat",
    section_path: list[str] | None = None,
    previous_chunk_id: str | None = None,
    next_chunk_id: str | None = None,
    parent_chunk_id: str | None = None,
) -> LexicalCandidate:
    return LexicalCandidate(
        chunk_id=chunk_id,
        document_id=document_id,
        rank=rank,
        raw_score=-1.0,
        score_direction="lower_is_better",
        chunk_type="subsection",
        source_ref={
            "source_id": "srd_35",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        locator={
            "section_path": section_path or ["Combat", "Attack of Opportunity"],
            "source_location": "test",
        },
        match_signals={
            "exact_phrase_hits": [],
            "protected_phrase_hits": [],
            "section_path_hit": False,
            "token_overlap_count": 0,
        },
        parent_chunk_id=parent_chunk_id,
        previous_chunk_id=previous_chunk_id,
        next_chunk_id=next_chunk_id,
    )


def _make_group(
    candidates: list[LexicalCandidate],
    *,
    document_id: str = "doc::combat",
    section_root: str = "Combat",
) -> CandidateGroup:
    return CandidateGroup(
        document_id=document_id,
        section_root=section_root,
        candidates=candidates,
        best_rank=candidates[0].rank if candidates else 0,
    )


def _consolidate_one(group: CandidateGroup) -> SpanGroup:
    return consolidate_adjacent([group])[0]


# ---------------------------------------------------------------------------
# Singleton: one candidate, no adjacency links
# ---------------------------------------------------------------------------


def test_singleton_group_emits_one_singleton_span():
    candidate = _make_candidate("chunk::A", rank=1)
    result = _consolidate_one(_make_group([candidate]))

    assert result.span_count == 1
    span = result.spans[0]
    assert span.chunk_ids == ("chunk::A",)
    assert span.start_chunk_id == "chunk::A"
    assert span.end_chunk_id == "chunk::A"
    assert span.merge_reason == "singleton"
    assert span.representative is candidate


# ---------------------------------------------------------------------------
# Adjacent pair: A.next == B.chunk_id, same section_path
# ---------------------------------------------------------------------------


def test_two_adjacent_chunks_merge_into_one_span():
    a = _make_candidate("chunk::A", rank=1, next_chunk_id="chunk::B")
    b = _make_candidate("chunk::B", rank=2, previous_chunk_id="chunk::A")
    result = _consolidate_one(_make_group([a, b]))

    assert result.span_count == 1
    span = result.spans[0]
    assert span.chunk_ids == ("chunk::A", "chunk::B")
    assert span.start_chunk_id == "chunk::A"
    assert span.end_chunk_id == "chunk::B"
    assert span.merge_reason == "adjacent_span"


# ---------------------------------------------------------------------------
# 1-2-3 chain: A → B → C, all in hit set, same section_path
# ---------------------------------------------------------------------------


def test_three_chained_chunks_merge_into_one_span():
    a = _make_candidate("chunk::A", rank=2, next_chunk_id="chunk::B")
    b = _make_candidate(
        "chunk::B",
        rank=1,  # best-ranked is in the middle
        previous_chunk_id="chunk::A",
        next_chunk_id="chunk::C",
    )
    c = _make_candidate("chunk::C", rank=3, previous_chunk_id="chunk::B")
    # Shuffle input order to prove the algorithm doesn't rely on it.
    result = _consolidate_one(_make_group([c, a, b]))

    assert result.span_count == 1
    span = result.spans[0]
    # Reading order is preserved regardless of input order or rank.
    assert span.chunk_ids == ("chunk::A", "chunk::B", "chunk::C")
    assert span.start_chunk_id == "chunk::A"
    assert span.end_chunk_id == "chunk::C"
    assert span.merge_reason == "adjacent_span"


# ---------------------------------------------------------------------------
# Gap: A, C in hit set, B not — NO bridging
# ---------------------------------------------------------------------------


def test_gap_in_hit_set_does_not_bridge():
    """A.next → B (missing from hit set), then B.next → C. A and C do not merge."""
    a = _make_candidate("chunk::A", rank=1, next_chunk_id="chunk::B")
    # B is not in the hit set.
    c = _make_candidate(
        "chunk::C",
        rank=2,
        previous_chunk_id="chunk::B",  # predecessor not in hit set → chain head
    )
    result = _consolidate_one(_make_group([a, c]))

    assert result.span_count == 2
    reasons = {s.merge_reason for s in result.spans}
    assert reasons == {"singleton"}
    chunk_ids = {s.chunk_ids for s in result.spans}
    assert chunk_ids == {("chunk::A",), ("chunk::C",)}


# ---------------------------------------------------------------------------
# Heading boundary: same section_root but different section_path
# ---------------------------------------------------------------------------


def test_same_section_root_but_different_section_path_does_not_merge():
    """Two hits chained via next/prev in the raw index but sitting in
    different sub-sections must stay as separate singletons."""
    a = _make_candidate(
        "chunk::A",
        rank=1,
        section_path=["Combat", "Attack Rolls"],
        next_chunk_id="chunk::B",
    )
    b = _make_candidate(
        "chunk::B",
        rank=2,
        section_path=["Combat", "Damage"],  # different sub-section
        previous_chunk_id="chunk::A",
    )
    result = _consolidate_one(_make_group([a, b]))

    assert result.span_count == 2
    for span in result.spans:
        assert span.merge_reason == "singleton"
        assert len(span.chunk_ids) == 1


# ---------------------------------------------------------------------------
# Representative selection: lowest rank, not necessarily start_chunk_id
# ---------------------------------------------------------------------------


def test_representative_is_best_ranked_not_start_chunk():
    """In a 3-chunk span A→B→C where B has the best (lowest) rank,
    representative is B while start_chunk_id stays A."""
    a = _make_candidate("chunk::A", rank=5, next_chunk_id="chunk::B")
    b = _make_candidate(
        "chunk::B",
        rank=1,
        previous_chunk_id="chunk::A",
        next_chunk_id="chunk::C",
    )
    c = _make_candidate("chunk::C", rank=3, previous_chunk_id="chunk::B")
    result = _consolidate_one(_make_group([a, b, c]))

    assert result.span_count == 1
    span = result.spans[0]
    assert span.representative.chunk_id == "chunk::B"
    assert span.representative.rank == 1
    assert span.start_chunk_id == "chunk::A"  # reading order, not rank
    assert span.end_chunk_id == "chunk::C"


# ---------------------------------------------------------------------------
# Multiple chains within one group
# ---------------------------------------------------------------------------


def test_multiple_disjoint_chains_in_one_group():
    """A→B are adjacent, D→E are adjacent, but B and D are not linked
    (or the link is broken by a missing chunk). Expect two 2-chunk spans."""
    a = _make_candidate("chunk::A", rank=1, next_chunk_id="chunk::B")
    b = _make_candidate(
        "chunk::B",
        rank=2,
        previous_chunk_id="chunk::A",
        next_chunk_id="chunk::C",  # C not in hit set → chain ends at B
    )
    d = _make_candidate(
        "chunk::D",
        rank=3,
        previous_chunk_id="chunk::C",  # predecessor not in hit set
        next_chunk_id="chunk::E",
    )
    e = _make_candidate("chunk::E", rank=4, previous_chunk_id="chunk::D")
    result = _consolidate_one(_make_group([a, b, d, e]))

    assert result.span_count == 2
    # Spans sorted by representative rank; first should be the A-B chain.
    assert result.spans[0].chunk_ids == ("chunk::A", "chunk::B")
    assert result.spans[1].chunk_ids == ("chunk::D", "chunk::E")
    for span in result.spans:
        assert span.merge_reason == "adjacent_span"


# ---------------------------------------------------------------------------
# Spans sorted by representative rank
# ---------------------------------------------------------------------------


def test_spans_sorted_by_representative_rank():
    """Multiple singletons in one group come out ordered by rank."""
    high = _make_candidate("chunk::H", rank=10)
    low = _make_candidate("chunk::L", rank=1)
    mid = _make_candidate("chunk::M", rank=5)
    result = _consolidate_one(_make_group([high, low, mid]))

    assert [s.representative.rank for s in result.spans] == [1, 5, 10]


# ---------------------------------------------------------------------------
# Empty group
# ---------------------------------------------------------------------------


def test_empty_group_produces_empty_span_group():
    group = CandidateGroup(
        document_id="doc::empty",
        section_root="Empty",
        candidates=[],
        best_rank=0,
    )
    result = _consolidate_one(group)

    assert result.spans == ()
    assert result.span_count == 0
    assert result.document_id == "doc::empty"
    assert result.section_root == "Empty"


# ---------------------------------------------------------------------------
# Cross-group isolation: consolidation never merges across CandidateGroups
# ---------------------------------------------------------------------------


def test_consolidation_never_merges_across_groups():
    """Even if one group's candidate has a next_chunk_id pointing to a
    chunk that exists in a different group, consolidation operates
    per-group and emits two SpanGroups."""
    a = _make_candidate("chunk::A", rank=1, next_chunk_id="chunk::X")
    x = _make_candidate(
        "chunk::X",
        rank=2,
        document_id="doc::spells",  # different document
        section_path=["Spells"],
        previous_chunk_id="chunk::A",
    )
    combat_group = _make_group([a], document_id="doc::combat", section_root="Combat")
    spells_group = _make_group([x], document_id="doc::spells", section_root="Spells")
    results = consolidate_adjacent([combat_group, spells_group])

    assert len(results) == 2
    for span_group in results:
        assert span_group.span_count == 1
        assert span_group.spans[0].merge_reason == "singleton"


# ---------------------------------------------------------------------------
# Batch: preserves input order
# ---------------------------------------------------------------------------


def test_consolidate_adjacent_preserves_group_order():
    a = _make_candidate("chunk::A", rank=1)
    b = _make_candidate(
        "chunk::B", rank=2, document_id="doc::spells", section_path=["Spells"]
    )
    groups = [
        _make_group([a], document_id="doc::combat", section_root="Combat"),
        _make_group([b], document_id="doc::spells", section_root="Spells"),
    ]
    results = consolidate_adjacent(groups)

    assert [g.section_root for g in results] == ["Combat", "Spells"]


# ---------------------------------------------------------------------------
# Cycle defence
# ---------------------------------------------------------------------------


def test_cycle_in_adjacency_does_not_infinite_loop():
    """Defensive: broken data with A.next=B, B.next=A shouldn't hang."""
    a = _make_candidate(
        "chunk::A", rank=1, previous_chunk_id="chunk::B", next_chunk_id="chunk::B"
    )
    b = _make_candidate(
        "chunk::B", rank=2, previous_chunk_id="chunk::A", next_chunk_id="chunk::A"
    )
    result = _consolidate_one(_make_group([a, b]))

    # We don't assert a specific span shape — only that we terminated and
    # every candidate was emitted somewhere.
    emitted_ids = {cid for span in result.spans for cid in span.chunk_ids}
    assert emitted_ids == {"chunk::A", "chunk::B"}
