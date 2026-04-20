"""Tests for Issue #43 lexical retriever end-to-end path."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.retrieval import NormalizedQuery
from scripts.retrieval.lexical_index import _search_raw, build_chunk_index


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
# Task 2: _build_fts_expression()
# ---------------------------------------------------------------------------

from scripts.retrieval.lexical_retriever import _build_fts_expression


def test_fts_expression_single_bare_token():
    query = NormalizedQuery(
        raw_query="fighter",
        normalized_text="fighter",
        tokens=["fighter"],
        protected_phrases=[],
        aliases_applied=[],
    )
    assert _build_fts_expression(query) == "fighter"


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
    assert result == '"fighter hit points" OR fighter OR "hit points"'


def test_fts_expression_multiple_bare_tokens():
    query = NormalizedQuery(
        raw_query="melee damage",
        normalized_text="melee damage",
        tokens=["melee", "damage"],
        protected_phrases=[],
        aliases_applied=[],
    )
    result = _build_fts_expression(query)
    assert result == '"melee damage" OR melee OR damage'


def test_fts_expression_empty_tokens_returns_empty_string():
    query = NormalizedQuery(
        raw_query="",
        normalized_text="",
        tokens=[],
        protected_phrases=[],
        aliases_applied=[],
    )
    assert _build_fts_expression(query) == ""
