"""Smoke tests for the retrieve_debug CLI output rendering.

The CLI itself is a dev tool, but its JSON mode is a documented output
contract.  These tests just verify that the JSON is serializable and
carries the expected top-level shape so changes to EvidenceItem /
PipelineTrace don't silently break the CLI.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.retrieval.lexical_index import build_chunk_index
from scripts.retrieve_debug import _to_json
from scripts.retrieval.evidence_pack import retrieve_evidence


def _write_chunk(path: Path, chunk: dict) -> Path:
    path.write_text(json.dumps(chunk), encoding="utf-8")
    return path


def _aoo_chunk() -> dict:
    return {
        "chunk_id": "chunk::srd_35::combat::001_aoo",
        "document_id": "srd_35::combat",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["Combat", "Attack of Opportunity"],
            "source_location": "Combat.rtf#001",
        },
        "chunk_type": "rule_section",
        "content": "An attack of opportunity is a single melee attack.",
    }


def test_to_json_is_serializable_for_singleton(tmp_path):
    db_path = tmp_path / "retrieval.db"
    _write_chunk(tmp_path / "aoo.json", _aoo_chunk())
    build_chunk_index(db_path, [tmp_path / "aoo.json"])

    pack = retrieve_evidence("attack of opportunity", db_path=db_path, top_k=5)
    payload = _to_json(pack)

    # Must round-trip through json.dumps without TypeError.
    serialized = json.dumps(payload)
    assert isinstance(serialized, str)

    assert set(payload.keys()) == {"query", "constraints", "trace", "evidence"}

    trace = payload["trace"]
    assert set(trace.keys()) == {"total_candidates", "group_count", "groups"}
    assert trace["group_count"] == 1
    assert trace["groups"][0]["candidate_count"] == 1
    assert trace["groups"][0]["span_count"] == 1

    assert len(payload["evidence"]) == 1
    item = payload["evidence"][0]
    # Span and adjacency are nested objects under this PR's contract.
    assert "span" in item
    assert set(item["span"].keys()) == {
        "chunk_ids",
        "start_chunk_id",
        "end_chunk_id",
        "merge_reason",
    }
    assert item["span"]["merge_reason"] == "singleton"
    assert "adjacency" in item
    assert set(item["adjacency"].keys()) == {
        "parent_chunk_id",
        "previous_chunk_id",
        "next_chunk_id",
    }


def test_to_json_for_adjacent_span(tmp_path):
    base = {
        "document_id": "srd_35::combat",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "chunk_type": "rule_section",
    }
    a = {
        **base,
        "chunk_id": "chunk::srd_35::combat::001_a",
        "locator": {
            "section_path": ["Combat", "Attack of Opportunity"],
            "source_location": "Combat.rtf#001",
        },
        "content": "AoO part one.",
        "next_chunk_id": "chunk::srd_35::combat::002_b",
    }
    b = {
        **base,
        "chunk_id": "chunk::srd_35::combat::002_b",
        "locator": {
            "section_path": ["Combat", "Attack of Opportunity"],
            "source_location": "Combat.rtf#002",
        },
        "content": "AoO part two.",
        "previous_chunk_id": "chunk::srd_35::combat::001_a",
    }
    db_path = tmp_path / "retrieval.db"
    _write_chunk(tmp_path / "a.json", a)
    _write_chunk(tmp_path / "b.json", b)
    build_chunk_index(db_path, [tmp_path / "a.json", tmp_path / "b.json"])

    pack = retrieve_evidence("attack of opportunity", db_path=db_path, top_k=5)
    payload = _to_json(pack)

    json.dumps(payload)  # serializability guard

    assert len(payload["evidence"]) == 1
    span = payload["evidence"][0]["span"]
    assert span["merge_reason"] == "adjacent_span"
    assert set(span["chunk_ids"]) == {a["chunk_id"], b["chunk_id"]}
