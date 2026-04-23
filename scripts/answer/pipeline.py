"""Answer pipeline orchestration and JSON serialization helpers.

``build_answer`` wires the assessor, composer, and citation binder into one
call that turns an ``EvidencePack`` into an ``AnswerResult``. The two
``to_*_json`` helpers are shared between the CLI and the tests so the
strict schema shape and the extended debug shape live in one place.
"""
from __future__ import annotations

from typing import Any

from scripts.retrieval.evidence_pack import EvidencePack

from .citation_binder import bind_citations
from .composer import _ComposedSegment, compose_segments
from .contracts import Abstention, AnswerResult, GroundedAnswer
from .support_assessor import assess_support


_ABSTAIN_REASONS: dict[str, str] = {
    "empty_evidence": "Insufficient evidence: no chunks retrieved for this query.",
    "weak_signals": "Insufficient evidence: retrieved chunks do not clearly match the query.",
}


def build_answer(pack: EvidencePack) -> AnswerResult:
    """Run the assessor → composer → binder pipeline against the pack."""
    assessment = assess_support(pack)
    query_text = pack.query.raw_query

    if assessment.outcome == "abstain":
        trigger = assessment.trigger_code
        assert trigger is not None  # invariant: abstain always has a trigger
        return Abstention(
            query=query_text,
            reason=_ABSTAIN_REASONS[trigger],
            trigger_code=trigger,
        )

    composed = compose_segments(pack)
    segments, citations = bind_citations(composed, pack)
    return GroundedAnswer(
        query=query_text,
        segments=segments,
        citations=citations,
    )


# ---------------------------------------------------------------------------
# JSON serialization (shared by CLI and tests)
# ---------------------------------------------------------------------------


def to_strict_json(result: AnswerResult, pack: EvidencePack) -> dict[str, Any]:
    """Serialize an ``AnswerResult`` to the strict schema shape (``--json``)."""
    if isinstance(result, Abstention):
        return {
            "query": result.query,
            "answer_type": "abstain",
            "abstention_reason": result.reason,
        }

    citations_payload = [
        {
            "citation_id": c.citation_id,
            "chunk_id": c.chunk_id,
            "source_ref": c.source_ref,
            "locator": c.locator,
            "excerpt": c.excerpt,
        }
        for c in result.citations
    ]
    selected_chunks = len({c.chunk_id for c in result.citations})

    return {
        "query": result.query,
        "answer_type": "grounded",
        "answer_segments": [
            {
                "segment_id": s.segment_id,
                "text": s.text,
                "support_type": s.support_type,
                "citation_ids": list(s.citation_ids),
            }
            for s in result.segments
        ],
        "citations": citations_payload,
        "retrieval_metadata": {
            "candidate_chunks": pack.trace.total_candidates,
            "selected_chunks": selected_chunks,
        },
    }


def to_debug_json(
    result: AnswerResult,
    pack: EvidencePack,
    composed_segments: tuple[_ComposedSegment, ...],
) -> dict[str, Any]:
    """Serialize to the extended ``--json-debug`` shape (non-schema-valid)."""
    payload = to_strict_json(result, pack)

    abstention_code: str | None = None
    selected_items: list[dict[str, Any]] = []
    if isinstance(result, Abstention):
        abstention_code = result.trigger_code
    else:
        for composed in composed_segments:
            item = composed.evidence_item
            selected_items.append(
                {
                    "chunk_id": item.chunk_id,
                    "rank": item.rank,
                    "match_signals": dict(item.match_signals),
                    "role": composed.role,
                }
            )

    payload["debug"] = {
        "abstention_code": abstention_code,
        "pipeline_trace": {
            "total_candidates": pack.trace.total_candidates,
            "group_count": pack.trace.group_count,
            "groups": [
                {
                    "document_id": gs.document_id,
                    "section_root": gs.section_root,
                    "candidate_count": gs.candidate_count,
                }
                for gs in pack.trace.group_summaries
            ],
        },
        "selected_items": selected_items,
    }
    return payload
