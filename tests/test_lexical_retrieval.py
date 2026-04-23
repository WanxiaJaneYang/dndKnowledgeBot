"""Tests for Issue #33 lexical retrieval baseline."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts.retrieval import (
    apply_filters,
    build_constraints,
    FilterResult,
    LexicalCandidate,
    NormalizedQuery,
    RetrievalConstraints,
    normalize_query,
)
from scripts.retrieval.lexical_index import _create_schema, build_chunk_index, search_chunk_index
from scripts.retrieval.match_signals import build_match_signals


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


@pytest.fixture
def title_only_chunk() -> dict:
    return {
        "chunk_id": "chunk::srd_35::combat::002_aoo_title_only",
        "document_id": "srd_35::combat::002_aoo_title_only",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["Combat", "Attack of Opportunity"],
            "source_location": "Combat.rtf#002_aoo_title_only",
        },
        "chunk_type": "subsection",
        "content": "This section explains when creatures threaten squares.",
    }


@pytest.fixture
def content_only_chunk() -> dict:
    return {
        "chunk_id": "chunk::srd_35::combat::003_aoo_content_only",
        "document_id": "srd_35::combat::003_aoo_content_only",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["Combat", "Threatened Squares"],
            "source_location": "Combat.rtf#003_aoo_content_only",
        },
        "chunk_type": "subsection",
        "content": "Sometimes movement provokes an attack of opportunity from a foe.",
    }


def _write_chunk(path: Path, chunk: dict) -> Path:
    path.write_text(json.dumps(chunk), encoding="utf-8")
    return path


def test_contract_exports_lexical_types() -> None:
    query = NormalizedQuery(
        raw_query="fighter hp",
        normalized_text="fighter hit points",
        tokens=["fighter", "hit points"],
        protected_phrases=["hit points"],
        aliases_applied=[{"source": "hp", "target": "hit points"}],
    )
    candidate = LexicalCandidate(
        chunk_id="chunk::srd_35::fighter::001_fighter",
        document_id="srd_35::fighter::001_fighter",
        rank=1,
        raw_score=-3.25,
        score_direction="lower_is_better",
        chunk_type="rule_section",
        source_ref={
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        locator={
            "section_path": ["Classes", "Fighter"],
            "source_location": "Classes.rtf#fighter",
        },
        match_signals={"token_overlap_count": 2},
    )

    assert query.normalized_text == "fighter hit points"
    assert candidate.chunk_id.endswith("fighter")
    assert candidate.score_direction == "lower_is_better"


def test_package_exports_preserve_filter_symbols() -> None:
    constraints = build_constraints()
    result = apply_filters([])

    assert isinstance(constraints, RetrievalConstraints)
    assert isinstance(result, FilterResult)


def test_from_query_normalization_adapts_real_payload() -> None:
    payload = normalize_query("fighter hp")

    query = NormalizedQuery.from_query_normalization(payload)

    assert query.raw_query == "fighter hp"
    assert query.normalized_text == "fighter hit points"
    assert query.tokens == ["fighter", "hit points"]
    assert query.aliases_applied == [{"source": "hp", "target": "hit points"}]


def test_from_query_normalization_requires_expected_keys() -> None:
    with pytest.raises(KeyError):
        NormalizedQuery.from_query_normalization(
            {
                "original_query": "fighter hp",
                "normalized_text": "fighter hit points",
            }
        )


def test_build_chunk_index_creates_fts_and_metadata_tables(tmp_path, sample_chunk) -> None:
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "attack_of_opportunity.json", sample_chunk)

    build_chunk_index(db_path, [chunk_path])

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        metadata_row = connection.execute(
            "SELECT section_path_text, chunk_type, source_ref_json, locator_json "
            "FROM chunk_metadata WHERE chunk_id = ?",
            (sample_chunk["chunk_id"],),
        ).fetchone()

    assert "chunk_metadata" in tables
    assert "chunks_fts" in tables
    assert metadata_row is not None
    assert metadata_row[0] == "Combat Attack of Opportunity"
    assert metadata_row[1] == "rule_section"
    assert json.loads(metadata_row[2])["source_id"] == "srd_35"
    assert json.loads(metadata_row[3])["section_path"] == ["Combat", "Attack of Opportunity"]


def test_search_chunk_index_returns_ranked_candidates_from_fts(tmp_path, sample_chunk) -> None:
    db_path = tmp_path / "retrieval.db"
    aoo_path = _write_chunk(tmp_path / "attack_of_opportunity.json", sample_chunk)
    turn_chunk = {
        **sample_chunk,
        "chunk_id": "chunk::srd_35::combat::004_turn_undead",
        "document_id": "srd_35::combat::004_turn_undead",
        "locator": {
            "section_path": ["Combat", "Turning Checks"],
            "source_location": "Combat.rtf#004_turn_undead",
        },
        "content": "Turning undead is a supernatural ability.",
    }
    turn_path = _write_chunk(tmp_path / "turn_undead.json", turn_chunk)

    build_chunk_index(db_path, [aoo_path, turn_path])
    results = search_chunk_index(db_path, "\"attack of opportunity\"", top_k=2)

    assert [result.rank for result in results] == [1]
    assert results[0].chunk_id == sample_chunk["chunk_id"]
    assert results[0].raw_score <= 0


def test_search_chunk_index_propagates_adjacency_fields(tmp_path, sample_chunk) -> None:
    """search_chunk_index also surfaces the adjacency fields (contract parity
    with retrieve_lexical)."""
    chunk_with_links = {
        **sample_chunk,
        "previous_chunk_id": "chunk::srd_35::combat::000_intro",
        "next_chunk_id": "chunk::srd_35::combat::002_flanking",
        "parent_chunk_id": "chunk::srd_35::combat::000_root",
    }
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "aoo.json", chunk_with_links)

    build_chunk_index(db_path, [chunk_path])
    results = search_chunk_index(db_path, "\"attack of opportunity\"", top_k=2)

    assert len(results) == 1
    candidate = results[0]
    assert candidate.parent_chunk_id == "chunk::srd_35::combat::000_root"
    assert candidate.previous_chunk_id == "chunk::srd_35::combat::000_intro"
    assert candidate.next_chunk_id == "chunk::srd_35::combat::002_flanking"


def test_search_chunk_index_adjacency_fields_null_when_absent(tmp_path, sample_chunk) -> None:
    """A chunk with no adjacency links yields None from search_chunk_index."""
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "aoo.json", sample_chunk)

    build_chunk_index(db_path, [chunk_path])
    results = search_chunk_index(db_path, "\"attack of opportunity\"", top_k=2)

    assert len(results) == 1
    candidate = results[0]
    assert candidate.parent_chunk_id is None
    assert candidate.previous_chunk_id is None
    assert candidate.next_chunk_id is None


def test_search_chunk_index_returns_empty_for_no_match(tmp_path, sample_chunk) -> None:
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "attack_of_opportunity.json", sample_chunk)

    build_chunk_index(db_path, [chunk_path])
    results = search_chunk_index(db_path, "\"turn undead\"", top_k=3)

    assert results == []


def test_search_chunk_index_returns_empty_for_zero_top_k(tmp_path, sample_chunk) -> None:
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "attack_of_opportunity.json", sample_chunk)

    build_chunk_index(db_path, [chunk_path])

    assert search_chunk_index(db_path, "\"attack of opportunity\"", top_k=0) == []


def test_search_chunk_index_orders_multiple_candidates_by_bm25(tmp_path, sample_chunk) -> None:
    db_path = tmp_path / "retrieval.db"
    stronger = {
        **sample_chunk,
        "chunk_id": "chunk::srd_35::combat::010_turn_undead_dense",
        "document_id": "srd_35::combat::010_turn_undead_dense",
        "locator": {
            "section_path": ["Combat", "Turning Checks"],
            "source_location": "Combat.rtf#010_turn_undead_dense",
        },
        "content": "Turn undead lets a cleric turn undead. A turn undead attempt affects undead.",
    }
    weaker = {
        **sample_chunk,
        "chunk_id": "chunk::srd_35::combat::011_turn_undead_sparse",
        "document_id": "srd_35::combat::011_turn_undead_sparse",
        "locator": {
            "section_path": ["Combat", "Turning"],
            "source_location": "Combat.rtf#011_turn_undead_sparse",
        },
        "content": "A cleric can turn undead with divine power.",
    }
    stronger_path = _write_chunk(tmp_path / "stronger.json", stronger)
    weaker_path = _write_chunk(tmp_path / "weaker.json", weaker)

    build_chunk_index(db_path, [stronger_path, weaker_path])
    results = search_chunk_index(db_path, "\"turn undead\"", top_k=2)

    assert [result.chunk_id for result in results] == [
        stronger["chunk_id"],
        weaker["chunk_id"],
    ]
    assert results[0].raw_score <= results[1].raw_score


def test_search_chunk_index_supports_real_corpus_turn_undead_recall(tmp_path) -> None:
    db_path = tmp_path / "retrieval.db"
    chunk_path = Path("data/chunks/srd_35/combatii__029_turning_checks.json")

    build_chunk_index(db_path, [chunk_path])
    results = search_chunk_index(db_path, "\"turn undead\"", top_k=3)

    assert results
    assert results[0].chunk_id == "chunk::srd_35::combatii::029_turning_checks"


def test_search_chunk_index_supports_real_corpus_bonus_feats_recall(tmp_path) -> None:
    db_path = tmp_path / "retrieval.db"
    chunk_path = Path("data/chunks/srd_35/feats__004_fighter_bonus_feats.json")

    build_chunk_index(db_path, [chunk_path])
    results = search_chunk_index(db_path, "\"fighter bonus feats\"", top_k=3)

    assert results
    assert results[0].chunk_id == "chunk::srd_35::feats::004_fighter_bonus_feats"


def test_build_chunk_index_rebuilds_cleanly(tmp_path, sample_chunk) -> None:
    db_path = tmp_path / "retrieval.db"
    first = _write_chunk(tmp_path / "first.json", sample_chunk)
    second_chunk = {
        **sample_chunk,
        "chunk_id": "chunk::srd_35::combat::005_turn_undead",
        "document_id": "srd_35::combat::005_turn_undead",
        "locator": {
            "section_path": ["Combat", "Turning Checks"],
            "source_location": "Combat.rtf#005_turn_undead",
        },
        "content": "Turn undead lets clerics repel undead creatures.",
    }
    second = _write_chunk(tmp_path / "second.json", second_chunk)

    build_chunk_index(db_path, [first])
    build_chunk_index(db_path, [second])

    stale = search_chunk_index(db_path, "\"attack of opportunity\"", top_k=3)
    fresh = search_chunk_index(db_path, "\"turn undead\"", top_k=3)

    assert stale == []
    assert fresh[0].chunk_id == second_chunk["chunk_id"]


def test_build_chunk_index_raises_on_malformed_chunk_shape(tmp_path) -> None:
    db_path = tmp_path / "retrieval.db"
    broken_chunk = {"chunk_id": "broken"}
    broken_path = _write_chunk(tmp_path / "broken.json", broken_chunk)

    with pytest.raises(KeyError):
        build_chunk_index(db_path, [broken_path])


def test_build_chunk_index_preserves_existing_index_when_rebuild_fails(tmp_path, sample_chunk) -> None:
    db_path = tmp_path / "retrieval.db"
    good_path = _write_chunk(tmp_path / "good.json", sample_chunk)
    broken_path = _write_chunk(tmp_path / "broken.json", {"chunk_id": "broken"})

    build_chunk_index(db_path, [good_path])

    with pytest.raises(KeyError):
        build_chunk_index(db_path, [broken_path])

    results = search_chunk_index(db_path, "\"attack of opportunity\"", top_k=3)

    assert [result.chunk_id for result in results] == [sample_chunk["chunk_id"]]


def test_create_schema_raises_when_fts5_is_unavailable(monkeypatch) -> None:
    class FakeConnection:
        def execute(self, sql: str):
            if "CREATE VIRTUAL TABLE chunks_fts USING fts5" in sql:
                raise sqlite3.OperationalError("no such module: fts5")
            return None

    with pytest.raises(RuntimeError, match="FTS5 support is required"):
        _create_schema(FakeConnection())


def test_build_match_signals_tracks_phrase_hits_in_title_only(title_only_chunk) -> None:
    query = NormalizedQuery(
        raw_query="attack of opportunity",
        normalized_text="attack of opportunity",
        tokens=["attack of opportunity"],
        protected_phrases=["attack of opportunity"],
        aliases_applied=[],
    )

    signals = build_match_signals(query, title_only_chunk, "Combat Attack of Opportunity")

    assert signals["exact_phrase_hits"] == ["attack of opportunity"]
    assert signals["protected_phrase_hits"] == ["attack of opportunity"]
    assert signals["section_path_hit"] is True
    assert signals["token_overlap_count"] == 3


def test_build_match_signals_tracks_phrase_hits_in_content_only(content_only_chunk) -> None:
    query = NormalizedQuery(
        raw_query="attack of opportunity",
        normalized_text="attack of opportunity",
        tokens=["attack of opportunity"],
        protected_phrases=["attack of opportunity"],
        aliases_applied=[],
    )

    signals = build_match_signals(query, content_only_chunk, "Combat Threatened Squares")

    assert signals["exact_phrase_hits"] == ["attack of opportunity"]
    assert signals["protected_phrase_hits"] == ["attack of opportunity"]
    assert signals["section_path_hit"] is False


def test_build_match_signals_reports_overlapping_protected_phrases(sample_chunk) -> None:
    query = NormalizedQuery(
        raw_query="fighter bab",
        normalized_text="fighter base attack bonus",
        tokens=["fighter", "base attack bonus"],
        protected_phrases=["base attack bonus", "attack bonus"],
        aliases_applied=[{"source": "bab", "target": "base attack bonus"}],
    )
    chunk = {
        **sample_chunk,
        "content": "A fighter's base attack bonus determines attack bonus progression.",
    }

    signals = build_match_signals(query, chunk, "Classes Fighter")

    assert signals["protected_phrase_hits"] == ["base attack bonus", "attack bonus"]
    assert signals["token_overlap_count"] >= 3


def test_build_match_signals_counts_token_overlap_across_section_and_content(sample_chunk) -> None:
    query = NormalizedQuery(
        raw_query="single melee attack",
        normalized_text="single melee attack",
        tokens=["single", "melee", "attack"],
        protected_phrases=[],
        aliases_applied=[],
    )

    signals = build_match_signals(query, sample_chunk, "Combat Attack of Opportunity")

    assert signals["exact_phrase_hits"] == ["single melee attack"]
    assert signals["protected_phrase_hits"] == []
    assert signals["section_path_hit"] is False
    assert signals["token_overlap_count"] == 3


def test_build_match_signals_does_not_mark_exact_phrase_inside_larger_word(sample_chunk) -> None:
    query = NormalizedQuery(
        raw_query="turn",
        normalized_text="turn",
        tokens=["turn"],
        protected_phrases=[],
        aliases_applied=[],
    )
    chunk = {
        **sample_chunk,
        "content": "Creatures can return to the fight after resting.",
    }

    signals = build_match_signals(query, chunk, "Combat Retreat")

    assert signals["exact_phrase_hits"] == []


def test_build_match_signals_does_not_mark_protected_phrase_inside_larger_word(sample_chunk) -> None:
    query = NormalizedQuery(
        raw_query="turn",
        normalized_text="turn",
        tokens=["turn"],
        protected_phrases=["turn"],
        aliases_applied=[],
    )
    chunk = {
        **sample_chunk,
        "content": "Creatures can return to the fight after resting.",
    }

    signals = build_match_signals(query, chunk, "Combat Retreat")

    assert signals["protected_phrase_hits"] == []
