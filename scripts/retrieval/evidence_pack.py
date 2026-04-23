"""Evidence-pack contract: retrieval-to-answer handoff.

The evidence pack wraps the final consolidated retrieval output with
enough context for answer generation to produce grounded, cited answers
without re-querying the index.  It also carries a pipeline trace so
retrieval behaviour is inspectable via the debug CLI.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .candidate_consolidation import SpanGroup, consolidate_adjacent
from .candidate_shaping import shape_candidates
from .contracts import MatchSignals, NormalizedQuery
from .filters import RetrievalConstraints, build_constraints
from .lexical_retriever import DEFAULT_DB_PATH, retrieve_lexical
from .query_normalization import normalize_query

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvidenceItem:
    """A single piece of evidence ready for answer generation.

    One EvidenceItem per EvidenceSpan.  Content is taken from the span's
    representative only — span content is deliberately *not* concatenated
    here (that is an answer-context-assembly concern, not a retrieval one).
    The other chunks in the span are carried as metadata via ``chunk_ids``
    so consumers can render "this evidence covers a run of N adjacent
    chunks".
    """

    chunk_id: str
    document_id: str
    rank: int
    content: str
    chunk_type: str
    source_ref: dict[str, Any]
    locator: dict[str, Any]
    match_signals: MatchSignals
    section_root: str
    # Span metadata (chunk_ids is in reading order; representative's
    # chunk_id need not equal start_chunk_id).
    chunk_ids: tuple[str, ...]
    start_chunk_id: str
    end_chunk_id: str
    merge_reason: str
    # Adjacency fields passed through from the representative.  Downstream
    # consumers (debug CLI, future answer-side span expansion) can use
    # these without reaching back into the original LexicalCandidate.
    parent_chunk_id: str | None
    previous_chunk_id: str | None
    next_chunk_id: str | None


@dataclass(frozen=True)
class GroupSummary:
    """Lightweight summary of one candidate group for the pipeline trace."""

    document_id: str
    section_root: str
    candidate_count: int
    span_count: int


@dataclass(frozen=True)
class PipelineTrace:
    """Diagnostic snapshot of the retrieval pipeline run."""

    total_candidates: int
    group_count: int
    group_summaries: tuple[GroupSummary, ...]


@dataclass(frozen=True)
class EvidencePack:
    """Complete retrieval-to-answer handoff contract.

    Contains everything answer generation needs: the evidence items (with
    content), query context, constraint summary, and a pipeline trace for
    debugging.
    """

    query: NormalizedQuery
    constraints_summary: dict[str, Any]
    evidence: tuple[EvidenceItem, ...]
    trace: PipelineTrace


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _fetch_content(db_path: Path, chunk_ids: list[str]) -> dict[str, str]:
    """Look up chunk content from the lexical index for a set of chunk_ids."""
    if not chunk_ids:
        return {}
    placeholders = ",".join("?" for _ in chunk_ids)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT chunk_id, content FROM chunk_metadata WHERE chunk_id IN ({placeholders})",
            chunk_ids,
        ).fetchall()
    return {row[0]: row[1] for row in rows}


def _constraints_to_summary(constraints: RetrievalConstraints) -> dict[str, Any]:
    return {
        "editions": sorted(constraints.editions),
        "source_types": sorted(constraints.source_types),
        "authority_levels": sorted(constraints.authority_levels),
        "excluded_source_ids": sorted(constraints.excluded_source_ids),
    }


def build_evidence_pack(
    query: NormalizedQuery,
    groups: list[SpanGroup],
    *,
    constraints: RetrievalConstraints,
    content_lookup: dict[str, str],
    total_candidates: int,
) -> EvidencePack:
    """Assemble an evidence pack from consolidated span groups.

    Parameters
    ----------
    query:
        The normalized query that produced the candidates.
    groups:
        Span groups from ``consolidate_adjacent()``.
    constraints:
        The retrieval constraints that were applied.
    content_lookup:
        Mapping of chunk_id → content text.  Only representative chunks
        need to be present; other chunks in a span are metadata and do
        not require hydration here.
    total_candidates:
        Number of candidates that entered shaping (before consolidation).
    """
    evidence: list[EvidenceItem] = []
    summaries: list[GroupSummary] = []
    missing_chunk_ids: list[str] = []

    for group in groups:
        candidate_count = sum(len(span.chunk_ids) for span in group.spans)
        summaries.append(
            GroupSummary(
                document_id=group.document_id,
                section_root=group.section_root,
                candidate_count=candidate_count,
                span_count=group.span_count,
            )
        )
        for span in group.spans:
            rep = span.representative
            content = content_lookup.get(rep.chunk_id, "")
            if not content:
                missing_chunk_ids.append(rep.chunk_id)
            evidence.append(
                EvidenceItem(
                    chunk_id=rep.chunk_id,
                    document_id=rep.document_id,
                    rank=rep.rank,
                    content=content,
                    chunk_type=rep.chunk_type,
                    source_ref=rep.source_ref,
                    locator=rep.locator,
                    match_signals=rep.match_signals,
                    section_root=group.section_root,
                    chunk_ids=span.chunk_ids,
                    start_chunk_id=span.start_chunk_id,
                    end_chunk_id=span.end_chunk_id,
                    merge_reason=span.merge_reason,
                    parent_chunk_id=rep.parent_chunk_id,
                    previous_chunk_id=rep.previous_chunk_id,
                    next_chunk_id=rep.next_chunk_id,
                )
            )

    if missing_chunk_ids:
        logger.warning(
            "No content found for %d chunk(s); evidence items will have empty content: %s",
            len(missing_chunk_ids),
            missing_chunk_ids,
        )

    trace = PipelineTrace(
        total_candidates=total_candidates,
        group_count=len(groups),
        group_summaries=tuple(summaries),
    )

    # Sort evidence globally by rank so consumers can iterate as-ranked
    # without needing to re-sort across groups.
    sorted_evidence = tuple(sorted(evidence, key=lambda e: e.rank))

    return EvidencePack(
        query=query,
        constraints_summary=_constraints_to_summary(constraints),
        evidence=sorted_evidence,
        trace=trace,
    )


def retrieve_evidence(
    raw_query: str,
    *,
    db_path: Path | None = None,
    top_k: int = 10,
) -> EvidencePack:
    """Full pipeline: raw query string → evidence pack.

    Runs normalization → lexical retrieval → shaping → adjacent-chunk
    consolidation → evidence pack assembly in one call.
    """
    norm_payload = normalize_query(raw_query)
    query = NormalizedQuery.from_query_normalization(norm_payload)
    constraints = build_constraints()
    effective_db = db_path or DEFAULT_DB_PATH

    candidates = retrieve_lexical(
        query, constraints=constraints, db_path=effective_db, top_k=top_k
    )
    groups = shape_candidates(candidates)
    span_groups = consolidate_adjacent(groups)

    # Only representative chunks need hydration — span metadata names the
    # other chunks but does not require their content here.
    chunk_ids = [
        span.representative.chunk_id
        for group in span_groups
        for span in group.spans
    ]
    content_lookup = _fetch_content(effective_db, chunk_ids)

    return build_evidence_pack(
        query,
        span_groups,
        constraints=constraints,
        content_lookup=content_lookup,
        total_candidates=len(candidates),
    )
