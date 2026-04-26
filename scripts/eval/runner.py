"""Run a single gold case through the answer pipeline and tag the outcome."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.answer.contracts import Abstention, GroundedAnswer
from scripts.answer.pipeline import build_answer
from scripts.retrieval.evidence_pack import retrieve_evidence

from .contracts import (
    ActualSummary,
    CaseOutcome,
    CitationSummary,
    GoldCase,
)
from .tagger import tag_case


def run_case(
    case: GoldCase,
    *,
    db_path: Path,
    top_k: int,
) -> CaseOutcome:
    """Retrieve, build an answer, tag it, and assemble a CaseOutcome."""
    pack = retrieve_evidence(case.question, db_path=db_path, top_k=top_k)
    result = build_answer(pack)
    tags, checks = tag_case(case, result, pack)

    if isinstance(result, GroundedAnswer):
        actual_answer_type = "grounded"
        primary = result.segments[0] if result.segments else None
        primary_excerpt = primary.text if primary is not None else None
        primary_support_type = primary.support_type if primary is not None else None
        citations = tuple(
            CitationSummary(
                citation_id=c.citation_id,
                chunk_id=c.chunk_id,
                source_id=str(c.source_ref.get("source_id", "")),
                edition=str(c.source_ref.get("edition", "")),
                section_path=tuple(c.locator.get("section_path", []) or []),
                entry_title=c.locator.get("entry_title"),
            )
            for c in result.citations
        )
        actual_summary = ActualSummary(
            primary_excerpt=primary_excerpt,
            primary_support_type=primary_support_type,
            citations=citations,
            abstention_reason=None,
        )
        abstention_code: str | None = None
    else:
        abstention: Abstention = result  # type: ignore[assignment]
        actual_answer_type = "abstain"
        actual_summary = ActualSummary(
            primary_excerpt=None,
            primary_support_type=None,
            citations=(),
            abstention_reason=abstention.reason,
        )
        abstention_code = abstention.trigger_code

    selected_chunks = (
        len({c.chunk_id for c in result.citations})
        if isinstance(result, GroundedAnswer)
        else 0
    )
    diagnostics: dict[str, Any] = {
        "abstention_code": abstention_code,
        "total_candidates": pack.trace.total_candidates,
        "selected_chunks": selected_chunks,
    }

    return CaseOutcome(
        eval_id=case.eval_id,
        question=case.question,
        question_type=case.question_type,
        expected_behavior=case.expected_behavior,
        actual_answer_type=actual_answer_type,
        tags=tags,
        actual_summary=actual_summary,
        citation_checks=checks,
        diagnostics=diagnostics,
    )
