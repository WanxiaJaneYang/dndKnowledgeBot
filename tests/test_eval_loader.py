"""Tests for ``scripts.eval.loader``."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.eval.loader import load_gold_set


_REPO_ROOT = Path(__file__).resolve().parents[1]
_GOLD_SET_PATH = _REPO_ROOT / "evals" / "phase1_gold.yaml"


def test_loads_phase1_gold_set_with_thirty_cases():
    cases = load_gold_set(_GOLD_SET_PATH)
    assert len(cases) == 30
    for case in cases:
        assert case.eval_id
        assert case.question
        assert case.question_type
        assert case.expected_behavior
        # expected_source_ids and expected_section_or_entry are tuples (possibly empty).
        assert isinstance(case.expected_source_ids, tuple)
        assert isinstance(case.expected_section_or_entry, tuple)


def test_abstain_cases_carry_empty_expected_lists():
    cases = load_gold_set(_GOLD_SET_PATH)
    abstain_cases = [c for c in cases if c.expected_behavior == "abstain"]
    assert abstain_cases  # sanity
    for case in abstain_cases:
        assert case.expected_source_ids == ()
        assert case.expected_section_or_entry == ()


def test_missing_required_field_raises_value_error(tmp_path):
    payload = {
        "dataset_id": "test",
        "cases": [
            {
                "eval_id": "X-001",
                "question": "What is X?",
                "question_type": "direct_lookup",
                "expected_source_ids": ["srd_35"],
                # missing expected_section_or_entry
                "expected_behavior": "direct_answer",
                "expected_answer_notes": "n/a",
            }
        ],
    }
    p = tmp_path / "broken.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ValueError) as exc_info:
        load_gold_set(p)
    assert "expected_section_or_entry" in str(exc_info.value)
