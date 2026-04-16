"""Tests for Issue #33 lexical retrieval baseline."""
from __future__ import annotations

import json
import sqlite3

import pytest

from scripts.retrieval import LexicalCandidate, NormalizedQuery
from scripts.retrieval.lexical_index import build_chunk_index
from scripts.retrieval.match_signals import build_match_signals


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


def test_build_chunk_index_creates_fts_and_metadata_tables(tmp_path, sample_chunk) -> None:
    db_path = tmp_path / "retrieval.db"
    chunk_path = tmp_path / "attack_of_opportunity.json"
    chunk_path.write_text(json.dumps(sample_chunk), encoding="utf-8")

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


def test_build_match_signals_tracks_exact_and_protected_phrases(sample_chunk) -> None:
    query = NormalizedQuery(
        raw_query="attack of opportunity",
        normalized_text="attack of opportunity",
        tokens=["attack of opportunity"],
        protected_phrases=["attack of opportunity"],
        aliases_applied=[],
    )

    signals = build_match_signals(query, sample_chunk, "Combat Attack of Opportunity")

    assert signals["exact_phrase_hits"] == ["attack of opportunity"]
    assert signals["protected_phrase_hits"] == ["attack of opportunity"]
    assert signals["section_path_hit"] is True


def test_build_match_signals_counts_token_overlap(sample_chunk) -> None:
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
