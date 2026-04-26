"""Tests for ``scripts.eval.report``."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.contracts import (
    ActualSummary,
    CaseOutcome,
    CitationCheck,
    CitationSummary,
)
from scripts.eval.report import build_report, write_json, write_markdown


def _make_outcome(
    *,
    eval_id: str,
    expected_behavior: str,
    actual_answer_type: str,
    tags: tuple[str, ...] = (),
    citations: tuple[CitationSummary, ...] = (),
    citation_checks: tuple[CitationCheck, ...] = (),
    primary_support_type: str | None = "direct_support",
) -> CaseOutcome:
    return CaseOutcome(
        eval_id=eval_id,
        question=f"q for {eval_id}",
        question_type="direct_lookup",
        expected_behavior=expected_behavior,  # type: ignore[arg-type]
        actual_answer_type=actual_answer_type,  # type: ignore[arg-type]
        tags=tags,
        actual_summary=ActualSummary(
            primary_excerpt="primary text" if actual_answer_type == "grounded" else None,
            primary_support_type=primary_support_type if actual_answer_type == "grounded" else None,
            citations=citations,
            abstention_reason=None if actual_answer_type == "grounded" else "no evidence",
        ),
        citation_checks=citation_checks,
        diagnostics={
            "abstention_code": None if actual_answer_type == "grounded" else "empty_evidence",
            "total_candidates": 0,
            "selected_chunks": len(citations),
        },
    )


def _make_summary(citation_id: str = "cit_1") -> CitationSummary:
    return CitationSummary(
        citation_id=citation_id,
        chunk_id=f"chunk::{citation_id}",
        source_id="srd_35",
        edition="3.5e",
        section_path=("Combat", "Attack of Opportunity"),
        entry_title=None,
    )


def _make_check(
    citation_id: str = "cit_1",
    *,
    section_match: bool | None = True,
    entry_match: bool | None = True,
    citation_mismatch: bool = False,
) -> CitationCheck:
    return CitationCheck(
        citation_id=citation_id,
        source_match=True,
        section_match=section_match,
        entry_match=entry_match,
        edition_match=True,
        token_overlap=("attack", "opportunity"),
        citation_mismatch=citation_mismatch,
    )


def test_build_report_counts_tags_and_clean_cases():
    outcomes = (
        _make_outcome(eval_id="P1-A", expected_behavior="direct_answer",
                      actual_answer_type="grounded", tags=()),
        _make_outcome(eval_id="P1-B", expected_behavior="direct_answer",
                      actual_answer_type="grounded",
                      tags=("retrieval_miss", "citation_mismatch")),
        _make_outcome(eval_id="P1-C", expected_behavior="abstain",
                      actual_answer_type="abstain", tags=()),
        _make_outcome(eval_id="P1-D", expected_behavior="direct_answer",
                      actual_answer_type="abstain", tags=("unnecessary_abstain",)),
    )
    report = build_report(outcomes, dataset_id="test_v1", run_started_at="2026-04-25T00:00:00Z")

    assert report.case_count == 4
    assert report.tag_counts["retrieval_miss"] == 1
    assert report.tag_counts["citation_mismatch"] == 1
    assert report.tag_counts["unnecessary_abstain"] == 1
    assert report.tag_counts["_clean"] == 2
    # 3 cases match expected behavior class (P1-A grounded, P1-B grounded,
    # P1-C abstain); P1-D is the only behavior mismatch → 3/4 = 0.75.
    assert report.behavior_match_rate == 0.75


def test_write_json_round_trips(tmp_path: Path):
    outcomes = (
        _make_outcome(
            eval_id="P1-X",
            expected_behavior="direct_answer",
            actual_answer_type="grounded",
            tags=(),
            citations=(_make_summary(),),
            citation_checks=(_make_check(),),
        ),
    )
    report = build_report(outcomes, dataset_id="ds", run_started_at="2026-04-25T00:00:00Z")
    out = tmp_path / "out.json"
    write_json(report, out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["dataset_id"] == "ds"
    assert payload["case_count"] == 1
    assert payload["tag_counts"]["_clean"] == 1
    assert payload["cases"][0]["eval_id"] == "P1-X"
    assert payload["cases"][0]["citation_checks"][0]["citation_id"] == "cit_1"


def test_write_markdown_includes_header_table_failing_block(tmp_path: Path):
    outcomes = (
        _make_outcome(
            eval_id="P1-FAIL",
            expected_behavior="direct_answer",
            actual_answer_type="grounded",
            tags=("retrieval_miss",),
            citations=(_make_summary(),),
            citation_checks=(_make_check(section_match=False, entry_match=False),),
        ),
        _make_outcome(eval_id="P1-OK", expected_behavior="direct_answer",
                      actual_answer_type="grounded", tags=()),
    )
    report = build_report(outcomes, dataset_id="ds", run_started_at="2026-04-25T00:00:00Z")
    out = tmp_path / "out.md"
    write_markdown(report, out)
    text = out.read_text(encoding="utf-8")
    assert "Phase 1 Gold-Set Eval" in text
    assert "Tag counts" in text
    assert "retrieval_miss" in text
    assert "P1-FAIL" in text
    # Clean tail collapsed to one summary line.
    assert "1 clean cases" in text
    assert "P1-OK" in text


def test_write_markdown_renders_n_a_when_section_match_is_none(tmp_path: Path):
    outcomes = (
        _make_outcome(
            eval_id="P1-AB",
            expected_behavior="abstain",
            actual_answer_type="grounded",
            tags=("missing_abstain",),
            citations=(_make_summary(),),
            citation_checks=(
                _make_check(section_match=None, entry_match=None),
            ),
        ),
    )
    report = build_report(outcomes, dataset_id="ds", run_started_at="2026-04-25T00:00:00Z")
    out = tmp_path / "out.md"
    write_markdown(report, out)
    text = out.read_text(encoding="utf-8")
    assert "n/a" in text
