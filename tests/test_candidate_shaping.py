"""Tests for candidate shaping (issue #44)."""
from __future__ import annotations

from scripts.retrieval.candidate_shaping import CandidateGroup, shape_candidates
from scripts.retrieval.contracts import LexicalCandidate


def _make_candidate(
    chunk_id: str,
    rank: int,
    section_path: list[str],
    *,
    raw_score: float = -1.0,
) -> LexicalCandidate:
    return LexicalCandidate(
        chunk_id=chunk_id,
        document_id=chunk_id.replace("chunk::", ""),
        rank=rank,
        raw_score=raw_score,
        score_direction="lower_is_better",
        chunk_type="subsection",
        source_ref={
            "source_id": "srd_35",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        locator={"section_path": section_path, "source_location": "test"},
        match_signals={
            "exact_phrase_hits": [],
            "protected_phrase_hits": [],
            "section_path_hit": False,
            "token_overlap_count": 0,
        },
    )


# ---------------------------------------------------------------------------
# Basic grouping
# ---------------------------------------------------------------------------


def test_shape_empty_returns_empty():
    assert shape_candidates([]) == []


def test_shape_single_candidate_returns_one_group():
    c = _make_candidate("chunk::combat::001", rank=1, section_path=["Combat", "Initiative"])
    groups = shape_candidates([c])

    assert len(groups) == 1
    assert groups[0].section_root == "Combat"
    assert groups[0].candidates == [c]
    assert groups[0].best_rank == 1
    assert groups[0].size == 1


def test_shape_groups_by_section_root():
    c1 = _make_candidate("chunk::combat::001", rank=1, section_path=["Combat", "Initiative"])
    c2 = _make_candidate("chunk::combat::002", rank=2, section_path=["Combat", "Attack of Opportunity"])
    c3 = _make_candidate("chunk::spells::001", rank=3, section_path=["Spells", "Fireball"])

    groups = shape_candidates([c1, c2, c3])

    assert len(groups) == 2
    assert groups[0].section_root == "Combat"
    assert groups[0].size == 2
    assert groups[1].section_root == "Spells"
    assert groups[1].size == 1


def test_shape_groups_sorted_by_best_rank():
    c1 = _make_candidate("chunk::spells::001", rank=1, section_path=["Spells", "Fireball"])
    c2 = _make_candidate("chunk::combat::001", rank=2, section_path=["Combat", "Initiative"])
    c3 = _make_candidate("chunk::combat::002", rank=3, section_path=["Combat", "AoO"])

    groups = shape_candidates([c1, c2, c3])

    assert groups[0].section_root == "Spells"
    assert groups[0].best_rank == 1
    assert groups[1].section_root == "Combat"
    assert groups[1].best_rank == 2


def test_shape_preserves_rank_order_within_group():
    c1 = _make_candidate("chunk::combat::003", rank=3, section_path=["Combat", "Damage"])
    c2 = _make_candidate("chunk::combat::001", rank=1, section_path=["Combat", "Initiative"])
    c3 = _make_candidate("chunk::combat::002", rank=2, section_path=["Combat", "AoO"])

    groups = shape_candidates([c1, c2, c3])

    assert len(groups) == 1
    assert [c.rank for c in groups[0].candidates] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_shape_handles_empty_section_path():
    c = _make_candidate("chunk::unknown::001", rank=1, section_path=[])
    groups = shape_candidates([c])

    assert len(groups) == 1
    assert groups[0].section_root == ""


def test_shape_handles_many_section_roots():
    candidates = [
        _make_candidate(f"chunk::s{i}::001", rank=i, section_path=[f"Section{i}", "Sub"])
        for i in range(1, 6)
    ]
    groups = shape_candidates(candidates)

    assert len(groups) == 5
    assert [g.best_rank for g in groups] == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Public export
# ---------------------------------------------------------------------------


def test_shape_candidates_importable_from_package():
    """Verify shape_candidates and CandidateGroup are importable from __init__."""
    from scripts.retrieval import CandidateGroup as CG, shape_candidates as sc
    assert sc is shape_candidates
    assert CG is CandidateGroup
