"""Tests for Issue #43 lexical retriever end-to-end path."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.retrieval import (
    LexicalCandidate,
    NormalizedQuery,
    build_constraints,
    normalize_query,
    retrieve_lexical as retrieve_lexical_public,
)
from scripts.retrieval.lexical_index import _search_raw, build_chunk_index
from scripts.retrieval.lexical_retriever import (
    _build_fts_expression,
    _composite_score,
    retrieve_lexical,
)


@pytest.fixture
def sample_chunk() -> dict:
    return {
        "chunk_id": "chunk::srd_35::combat::001_attack_of_opportunity",
        "document_id": "srd_35::combat::001_attack_of_opportunity",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["Combat", "Attack of Opportunity"],
            "source_location": "Combat.rtf#001_attack_of_opportunity",
        },
        "chunk_type": "rule_section",
        "content": "An attack of opportunity is a single melee attack.",
    }


def _write_chunk(path: Path, chunk: dict) -> Path:
    path.write_text(json.dumps(chunk), encoding="utf-8")
    return path


def test_search_raw_returns_row_data_with_content(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "aoo.json", sample_chunk)
    build_chunk_index(db_path, [chunk_path])

    rows = _search_raw(db_path, '"attack of opportunity"', top_k=3)

    assert len(rows) == 1
    row = rows[0]
    assert row["chunk_id"] == sample_chunk["chunk_id"]
    assert row["content"] == sample_chunk["content"]
    assert row["section_path_text"] == "Combat Attack of Opportunity"
    assert row["source_ref"] == sample_chunk["source_ref"]
    assert row["locator"] == sample_chunk["locator"]
    assert row["raw_score"] <= 0


# ---------------------------------------------------------------------------
# _build_fts_expression()
# ---------------------------------------------------------------------------


def test_fts_expression_single_bare_token():
    query = NormalizedQuery(
        raw_query="fighter",
        normalized_text="fighter",
        tokens=["fighter"],
        protected_phrases=[],
        aliases_applied=[],
    )
    assert _build_fts_expression(query) == '"fighter"'


def test_fts_expression_protected_phrase_quoted():
    query = NormalizedQuery(
        raw_query="hit points",
        normalized_text="hit points",
        tokens=["hit points"],
        protected_phrases=["hit points"],
        aliases_applied=[],
    )
    assert _build_fts_expression(query) == '"hit points"'


def test_fts_expression_mixed_tokens_and_protected_phrases():
    query = NormalizedQuery(
        raw_query="fighter hp",
        normalized_text="fighter hit points",
        tokens=["fighter", "hit points"],
        protected_phrases=["hit points"],
        aliases_applied=[{"source": "hp", "target": "hit points"}],
    )
    result = _build_fts_expression(query)
    assert result == '"fighter hit points" OR "fighter" OR "hit points"'


def test_fts_expression_multiple_bare_tokens():
    query = NormalizedQuery(
        raw_query="melee damage",
        normalized_text="melee damage",
        tokens=["melee", "damage"],
        protected_phrases=[],
        aliases_applied=[],
    )
    result = _build_fts_expression(query)
    assert result == '"melee damage" OR "melee" OR "damage"'


def test_fts_expression_empty_tokens_returns_empty_string():
    query = NormalizedQuery(
        raw_query="",
        normalized_text="",
        tokens=[],
        protected_phrases=[],
        aliases_applied=[],
    )
    assert _build_fts_expression(query) == ""


# ---------------------------------------------------------------------------
# retrieve_lexical()
# ---------------------------------------------------------------------------


def test_retrieve_lexical_returns_candidates_with_populated_signals(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "aoo.json", sample_chunk)
    build_chunk_index(db_path, [chunk_path])

    query = NormalizedQuery(
        raw_query="attack of opportunity",
        normalized_text="attack of opportunity",
        tokens=["attack of opportunity"],
        protected_phrases=["attack of opportunity"],
        aliases_applied=[],
    )
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert len(results) == 1
    candidate = results[0]
    assert isinstance(candidate, LexicalCandidate)
    assert candidate.chunk_id == sample_chunk["chunk_id"]
    assert candidate.rank == 1
    assert candidate.match_signals["exact_phrase_hits"] == ["attack of opportunity"]
    assert candidate.match_signals["protected_phrase_hits"] == ["attack of opportunity"]
    assert candidate.match_signals["section_path_hit"] is True
    assert candidate.match_signals["token_overlap_count"] >= 3


def test_retrieve_lexical_filters_out_non_matching_editions(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunk_5e = {
        **sample_chunk,
        "chunk_id": "chunk::phb_5e::combat::001",
        "source_ref": {
            **sample_chunk["source_ref"],
            "source_id": "phb_5e",
            "edition": "5e",
            "source_type": "core_rulebook",
            "authority_level": "official",
        },
    }
    path_35 = _write_chunk(tmp_path / "aoo_35.json", sample_chunk)
    path_5e = _write_chunk(tmp_path / "aoo_5e.json", chunk_5e)
    build_chunk_index(db_path, [path_35, path_5e])

    query = NormalizedQuery(
        raw_query="attack of opportunity",
        normalized_text="attack of opportunity",
        tokens=["attack of opportunity"],
        protected_phrases=["attack of opportunity"],
        aliases_applied=[],
    )
    constraints = build_constraints()
    results = retrieve_lexical(query, constraints=constraints, db_path=db_path, top_k=5)

    assert all(r.source_ref["edition"] == "3.5e" for r in results)
    assert len(results) == 1


def test_retrieve_lexical_returns_empty_for_no_match(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "aoo.json", sample_chunk)
    build_chunk_index(db_path, [chunk_path])

    query = NormalizedQuery(
        raw_query="psionics",
        normalized_text="psionics",
        tokens=["psionics"],
        protected_phrases=[],
        aliases_applied=[],
    )
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert results == []


def test_retrieve_lexical_empty_tokens_returns_empty(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "aoo.json", sample_chunk)
    build_chunk_index(db_path, [chunk_path])

    query = NormalizedQuery(
        raw_query="",
        normalized_text="",
        tokens=[],
        protected_phrases=[],
        aliases_applied=[],
    )
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert results == []


def test_retrieve_lexical_respects_top_k(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunks = []
    for i in range(5):
        chunk = {
            **sample_chunk,
            "chunk_id": f"chunk::srd_35::combat::{i:03d}_attack",
            "document_id": f"srd_35::combat::{i:03d}_attack",
            "content": f"An attack of opportunity is a melee attack variant {i}.",
        }
        chunks.append(_write_chunk(tmp_path / f"chunk_{i}.json", chunk))
    build_chunk_index(db_path, chunks)

    query = NormalizedQuery(
        raw_query="attack of opportunity",
        normalized_text="attack of opportunity",
        tokens=["attack of opportunity"],
        protected_phrases=["attack of opportunity"],
        aliases_applied=[],
    )
    results = retrieve_lexical(query, db_path=db_path, top_k=3)

    assert len(results) == 3
    assert [r.rank for r in results] == [1, 2, 3]


def test_retrieve_lexical_reranks_after_filtering(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunk_35 = sample_chunk
    chunk_5e = {
        **sample_chunk,
        "chunk_id": "chunk::phb_5e::combat::001",
        "document_id": "phb_5e::combat::001",
        "source_ref": {
            **sample_chunk["source_ref"],
            "source_id": "phb_5e",
            "edition": "5e",
            "source_type": "core_rulebook",
            "authority_level": "official",
        },
    }
    path_35 = _write_chunk(tmp_path / "aoo_35.json", chunk_35)
    path_5e = _write_chunk(tmp_path / "aoo_5e.json", chunk_5e)
    build_chunk_index(db_path, [path_35, path_5e])

    query = NormalizedQuery(
        raw_query="attack of opportunity",
        normalized_text="attack of opportunity",
        tokens=["attack of opportunity"],
        protected_phrases=["attack of opportunity"],
        aliases_applied=[],
    )
    constraints = build_constraints()
    results = retrieve_lexical(query, constraints=constraints, db_path=db_path, top_k=5)

    assert len(results) == 1
    assert results[0].rank == 1


# ---------------------------------------------------------------------------
# Domain-aware reranking
# ---------------------------------------------------------------------------


def test_reranking_promotes_section_path_hit_over_content_only(tmp_path, sample_chunk):
    """A chunk whose section path matches the query should rank above one
    that only matches in content, even if BM25 scores are similar."""
    db_path = tmp_path / "retrieval.db"

    # This chunk mentions "turn undead" only in content — no section path match.
    content_only = {
        **sample_chunk,
        "chunk_id": "chunk::srd_35::spells::001_content_only",
        "document_id": "srd_35::spells::001_content_only",
        "locator": {
            "section_path": ["Spells", "Cleric Spells"],
            "source_location": "Spells.rtf#001_content_only",
        },
        "content": "This ability allows the cleric to turn undead creatures using divine energy. "
                   "Turn undead is a supernatural ability that uses turn undead checks.",
    }

    # This chunk has "turn undead" in the section path *and* content.
    section_hit = {
        **sample_chunk,
        "chunk_id": "chunk::srd_35::combat::002_section_hit",
        "document_id": "srd_35::combat::002_section_hit",
        "locator": {
            "section_path": ["Combat", "Turn Undead"],
            "source_location": "Combat.rtf#002_section_hit",
        },
        "content": "A cleric can turn undead.",
    }

    path_content = _write_chunk(tmp_path / "content_only.json", content_only)
    path_section = _write_chunk(tmp_path / "section_hit.json", section_hit)
    build_chunk_index(db_path, [path_content, path_section])

    query = NormalizedQuery(
        raw_query="turn undead",
        normalized_text="turn undead",
        tokens=["turn undead"],
        protected_phrases=["turn undead"],
        aliases_applied=[],
    )
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert len(results) == 2
    # The section-path-hit chunk should be ranked first despite potentially
    # weaker BM25 (fewer repetitions of "turn undead" in content).
    assert results[0].chunk_id == section_hit["chunk_id"]
    assert results[0].match_signals["section_path_hit"] is True


def test_reranking_promotes_protected_phrase_hit(tmp_path, sample_chunk):
    """A chunk matching a protected phrase should rank above one with only
    bare token overlap, given similar BM25 scores."""
    db_path = tmp_path / "retrieval.db"

    # Matches "fighter" and "base attack" tokens but does NOT contain the
    # protected phrase "base attack bonus" as a unit.
    partial = {
        **sample_chunk,
        "chunk_id": "chunk::srd_35::combat::001_partial",
        "document_id": "srd_35::combat::001_partial",
        "locator": {
            "section_path": ["Combat", "Attack Actions"],
            "source_location": "Combat.rtf#001_partial",
        },
        "content": "A fighter makes a base attack roll to determine whether the attack hits. "
                   "The fighter base attack roll is base attack plus modifiers.",
    }

    # Contains the exact protected phrase "base attack bonus".
    exact = {
        **sample_chunk,
        "chunk_id": "chunk::srd_35::combat::002_exact",
        "document_id": "srd_35::combat::002_exact",
        "locator": {
            "section_path": ["Combat", "Base Attack Bonus"],
            "source_location": "Combat.rtf#002_exact",
        },
        "content": "A fighter's base attack bonus increases with level.",
    }

    path_partial = _write_chunk(tmp_path / "partial.json", partial)
    path_exact = _write_chunk(tmp_path / "exact.json", exact)
    build_chunk_index(db_path, [path_partial, path_exact])

    query = NormalizedQuery(
        raw_query="fighter bab",
        normalized_text="fighter base attack bonus",
        tokens=["fighter", "base attack bonus"],
        protected_phrases=["base attack bonus"],
        aliases_applied=[{"source": "bab", "target": "base attack bonus"}],
    )
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert len(results) == 2
    assert results[0].chunk_id == exact["chunk_id"]
    assert results[0].match_signals["section_path_hit"] is True


# ---------------------------------------------------------------------------
# _composite_score()
# ---------------------------------------------------------------------------


def test_composite_score_section_path_hit_beats_no_hit():
    base = {"exact_phrase_hits": [], "protected_phrase_hits": [], "section_path_hit": False, "token_overlap_count": 0}
    boosted = {**base, "section_path_hit": True}
    assert _composite_score(-1.0, boosted) < _composite_score(-1.0, base)


def test_composite_score_exact_phrase_hit_beats_no_hit():
    base = {"exact_phrase_hits": [], "protected_phrase_hits": [], "section_path_hit": False, "token_overlap_count": 0}
    boosted = {**base, "exact_phrase_hits": ["attack of opportunity"]}
    assert _composite_score(-1.0, boosted) < _composite_score(-1.0, base)


def test_composite_score_token_overlap_contributes():
    base = {"exact_phrase_hits": [], "protected_phrase_hits": [], "section_path_hit": False, "token_overlap_count": 1}
    more = {**base, "token_overlap_count": 5}
    assert _composite_score(-1.0, more) < _composite_score(-1.0, base)


def test_composite_score_all_signals_compound():
    none = {"exact_phrase_hits": [], "protected_phrase_hits": [], "section_path_hit": False, "token_overlap_count": 0}
    all_signals = {
        "exact_phrase_hits": ["turn undead"],
        "protected_phrase_hits": ["turn undead"],
        "section_path_hit": True,
        "token_overlap_count": 3,
    }
    assert _composite_score(-1.0, all_signals) < _composite_score(-1.0, none)


# ---------------------------------------------------------------------------
# Real-corpus recall tests
# ---------------------------------------------------------------------------


def _build_index_with_real_chunks(db_path: Path, chunk_filenames: list[str]) -> None:
    chunk_dir = Path("data/chunks/srd_35")
    chunk_paths = [chunk_dir / name for name in chunk_filenames]
    build_chunk_index(db_path, chunk_paths)


def test_real_corpus_recall_turn_undead(tmp_path):
    db_path = tmp_path / "retrieval.db"
    _build_index_with_real_chunks(db_path, ["combatii__029_turning_checks.json"])

    payload = normalize_query("turn undead")
    query = NormalizedQuery.from_query_normalization(payload)
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert results
    assert results[0].chunk_id == "chunk::srd_35::combatii::029_turning_checks"
    assert results[0].match_signals["token_overlap_count"] >= 2


def test_real_corpus_recall_attack_of_opportunity(tmp_path):
    db_path = tmp_path / "retrieval.db"
    _build_index_with_real_chunks(db_path, [
        "combati__001_combati.json",
        "combati__002_how_combat_works.json",
        "combati__014_attacks_of_opportunity.json",
    ])

    payload = normalize_query("attack of opportunity")
    query = NormalizedQuery.from_query_normalization(payload)
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert results
    chunk_ids = [r.chunk_id for r in results]
    assert "chunk::srd_35::combati::014_attacks_of_opportunity" in chunk_ids


def test_real_corpus_recall_fighter_bonus_feats(tmp_path):
    db_path = tmp_path / "retrieval.db"
    _build_index_with_real_chunks(db_path, ["feats__004_fighter_bonus_feats.json"])

    payload = normalize_query("fighter bonus feats")
    query = NormalizedQuery.from_query_normalization(payload)
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert results
    assert results[0].chunk_id == "chunk::srd_35::feats::004_fighter_bonus_feats"
    assert results[0].match_signals["token_overlap_count"] >= 2


def test_retrieve_lexical_public_export(tmp_path, sample_chunk):
    """Verify retrieve_lexical is importable from the package-level __init__."""
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "aoo.json", sample_chunk)
    build_chunk_index(db_path, [chunk_path])

    query = NormalizedQuery(
        raw_query="attack of opportunity",
        normalized_text="attack of opportunity",
        tokens=["attack of opportunity"],
        protected_phrases=["attack of opportunity"],
        aliases_applied=[],
    )
    results = retrieve_lexical_public(query, db_path=db_path, top_k=5)
    assert len(results) == 1
