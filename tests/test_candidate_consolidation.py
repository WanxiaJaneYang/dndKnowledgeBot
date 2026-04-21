"""Tests for candidate consolidation (issue #34)."""
from __future__ import annotations

from scripts.retrieval.candidate_consolidation import (
    ConsolidatedCandidate,
    ConsolidatedGroup,
    consolidate_candidates,
    consolidate_group,
)
from scripts.retrieval.candidate_shaping import CandidateGroup
from scripts.retrieval.contracts import LexicalCandidate


def _make_candidate(
    chunk_id: str,
    document_id: str,
    rank: int,
    section_path: list[str] | None = None,
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
            "section_path": section_path or ["Combat", "Test"],
            "source_location": "test",
        },
        match_signals={
            "exact_phrase_hits": [],
            "protected_phrase_hits": [],
            "section_path_hit": False,
            "token_overlap_count": 0,
        },
    )


def _make_group(
    section_root: str,
    candidates: list[LexicalCandidate],
    document_id: str = "doc::test",
) -> CandidateGroup:
    return CandidateGroup(
        document_id=document_id,
        section_root=section_root,
        candidates=candidates,
        best_rank=candidates[0].rank if candidates else 0,
    )


# ---------------------------------------------------------------------------
# consolidate_group
# ---------------------------------------------------------------------------


def test_consolidate_group_no_duplicates():
    """All unique document_ids → nothing dropped."""
    candidates = [
        _make_candidate("chunk::001", "doc::001", rank=1),
        _make_candidate("chunk::002", "doc::002", rank=2),
    ]
    group = _make_group("Combat", candidates)
    result = consolidate_group(group)

    assert result.size == 2
    assert result.dropped_count == 0
    assert all(c.merge_reason == "unique" for c in result.candidates)


def test_consolidate_group_merges_same_document():
    """Two candidates from the same document_id → merged into one."""
    candidates = [
        _make_candidate("chunk::001", "doc::combat", rank=1),
        _make_candidate("chunk::002", "doc::combat", rank=2),
        _make_candidate("chunk::003", "doc::spells", rank=3),
    ]
    group = _make_group("Combat", candidates)
    result = consolidate_group(group)

    assert result.size == 2
    assert result.dropped_count == 1

    # The representative should be the higher-ranked one
    combat_consolidated = [c for c in result.candidates if c.chunk_id == "chunk::001"][0]
    assert combat_consolidated.merged_chunk_ids == ["chunk::001", "chunk::002"]
    assert combat_consolidated.merge_reason == "same_document"
    assert combat_consolidated.rank == 1


def test_consolidate_group_preserves_rank_order():
    """Consolidated candidates are sorted by rank."""
    candidates = [
        _make_candidate("chunk::003", "doc::spells", rank=3),
        _make_candidate("chunk::001", "doc::combat", rank=1),
        _make_candidate("chunk::002", "doc::combat", rank=2),
    ]
    group = _make_group("Mixed", candidates)
    result = consolidate_group(group)

    ranks = [c.rank for c in result.candidates]
    assert ranks == sorted(ranks)


def test_consolidate_group_preserves_provenance():
    """All original chunk_ids are recorded in merged_chunk_ids."""
    candidates = [
        _make_candidate("chunk::001", "doc::combat", rank=1),
        _make_candidate("chunk::002", "doc::combat", rank=2),
        _make_candidate("chunk::003", "doc::combat", rank=3),
    ]
    group = _make_group("Combat", candidates)
    result = consolidate_group(group)

    assert result.size == 1
    assert result.dropped_count == 2
    assert result.candidates[0].merged_chunk_ids == [
        "chunk::001", "chunk::002", "chunk::003"
    ]


def test_consolidate_group_picks_best_rank_regardless_of_input_order():
    """Even if the lower-ranked candidate appears first, the best-ranked wins."""
    candidates = [
        _make_candidate("chunk::002", "doc::combat", rank=5),
        _make_candidate("chunk::001", "doc::combat", rank=1),
    ]
    group = _make_group("Combat", candidates)
    result = consolidate_group(group)

    assert result.size == 1
    assert result.candidates[0].chunk_id == "chunk::001"
    assert result.candidates[0].rank == 1
    assert set(result.candidates[0].merged_chunk_ids) == {"chunk::001", "chunk::002"}


def test_consolidate_group_empty():
    group = _make_group("Empty", [])
    result = consolidate_group(group)
    assert result.size == 0
    assert result.dropped_count == 0


# ---------------------------------------------------------------------------
# consolidate_candidates
# ---------------------------------------------------------------------------


def test_consolidate_candidates_processes_all_groups():
    groups = [
        _make_group("Combat", [
            _make_candidate("chunk::001", "doc::001", rank=1),
        ]),
        _make_group("Spells", [
            _make_candidate("chunk::002", "doc::002", rank=2),
            _make_candidate("chunk::003", "doc::002", rank=3),
        ]),
    ]
    results = consolidate_candidates(groups)

    assert len(results) == 2
    assert results[0].section_root == "Combat"
    assert results[0].size == 1
    assert results[1].section_root == "Spells"
    assert results[1].size == 1
    assert results[1].dropped_count == 1


# ---------------------------------------------------------------------------
# Public export
# ---------------------------------------------------------------------------


def test_consolidation_importable_from_package():
    from scripts.retrieval import (
        ConsolidatedCandidate as CC,
        ConsolidatedGroup as CG,
        consolidate_candidates as cc,
    )
    assert cc is consolidate_candidates
    assert CC is ConsolidatedCandidate
    assert CG is ConsolidatedGroup
