"""End-to-end smoke test for ``scripts.eval.runner.run_case``."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.contracts import GoldCase
from scripts.eval.runner import run_case
from scripts.retrieval.lexical_index import build_chunk_index


def _make_chunk_dir(tmp_path: Path) -> Path:
    """Build a tiny chunk index containing a single AoO chunk."""
    chunk = {
        "chunk_id": "chunk::srd_35::combat::001_attack_of_opportunity",
        "document_id": "srd_35::combat",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["Combat: Attacks of Opportunity", "Movement"],
            "source_location": "CombatI.rtf#001",
        },
        "chunk_type": "rule_section",
        "content": (
            "A character provokes an attack of opportunity when leaving a "
            "threatened square through movement."
        ),
    }
    chunk_path = tmp_path / "aoo.json"
    chunk_path.write_text(json.dumps(chunk), encoding="utf-8")
    db_path = tmp_path / "lexical.db"
    build_chunk_index(db_path, [chunk_path])
    return db_path


def test_runner_grounded_clean_case(tmp_path: Path):
    db_path = _make_chunk_dir(tmp_path)
    case = GoldCase(
        eval_id="P1-T-001",
        question="When does a character provoke an attack of opportunity?",
        question_type="direct_lookup",
        expected_source_ids=("srd_35",),
        expected_section_or_entry=(
            "Combat: Attacks of Opportunity",
            "Movement",
        ),
        expected_behavior="direct_answer",
        expected_answer_notes="",
    )
    outcome = run_case(case, db_path=db_path, top_k=5)
    assert outcome.eval_id == "P1-T-001"
    assert outcome.actual_answer_type == "grounded"
    # All citations match → clean tags.
    assert outcome.tags == ()
    assert outcome.diagnostics["total_candidates"] >= 1


def test_runner_abstain_case_against_unrelated_query(tmp_path: Path):
    db_path = _make_chunk_dir(tmp_path)
    case = GoldCase(
        eval_id="P1-IE-001",
        question="What are Artificer infusion slots at level 5?",
        question_type="insufficient_evidence",
        expected_source_ids=(),
        expected_section_or_entry=(),
        expected_behavior="abstain",
        expected_answer_notes="",
    )
    outcome = run_case(case, db_path=db_path, top_k=5)
    # Index has no Artificer content → retrieve_evidence returns empty →
    # build_answer abstains.
    assert outcome.actual_answer_type == "abstain"
    assert outcome.tags == ()  # behavior matches expected abstain
    assert outcome.diagnostics["abstention_code"] in {
        "empty_evidence", "weak_signals"
    }


def test_runner_grounded_when_abstain_expected(tmp_path: Path):
    db_path = _make_chunk_dir(tmp_path)
    # Question matches the only chunk, but the gold case expects abstain.
    case = GoldCase(
        eval_id="P1-IE-X",
        question="When does a character provoke an attack of opportunity?",
        question_type="insufficient_evidence",
        expected_source_ids=(),
        expected_section_or_entry=(),
        expected_behavior="abstain",
        expected_answer_notes="",
    )
    outcome = run_case(case, db_path=db_path, top_k=5)
    if outcome.actual_answer_type == "grounded":
        assert "missing_abstain" in outcome.tags
        # Section/entry checks short-circuited for empty expected list.
        for check in outcome.citation_checks:
            assert check.section_match is None
            assert check.entry_match is None
