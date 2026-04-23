"""Evidence-pack contract: retrieval-to-answer handoff.

The evidence pack wraps the final shaped retrieval output with enough
context for answer generation to produce grounded, cited answers without
re-querying the index.  It also carries a pipeline trace so retrieval
behaviour is inspectable via the debug CLI.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from .candidate_shaping import CandidateGroup
from .contracts import MatchSignals, NormalizedQuery
from .filters import RetrievalConstraints


@dataclass(frozen=True)
class EvidenceItem:
    """A single piece of evidence ready for answer generation."""

    chunk_id: str
    document_id: str
    rank: int
    content: str
    chunk_type: str
    source_ref: dict[str, Any]
    locator: dict[str, Any]
    match_signals: MatchSignals
    section_root: str


@dataclass(frozen=True)
class GroupSummary:
    """Lightweight summary of one candidate group for the pipeline trace."""

    document_id: str
    section_root: str
    candidate_count: int


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
    evidence: list[EvidenceItem]
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
    groups: list[CandidateGroup],
    *,
    constraints: RetrievalConstraints,
    content_lookup: dict[str, str],
    total_candidates: int,
) -> EvidencePack:
    """Assemble an evidence pack from shaped candidate groups.

    Parameters
    ----------
    query:
        The normalized query that produced the candidates.
    groups:
        Candidate groups from ``shape_candidates()``.
    constraints:
        The retrieval constraints that were applied.
    content_lookup:
        Mapping of chunk_id → content text for candidate chunks.
    total_candidates:
        Number of candidates that entered shaping.
    """
    evidence: list[EvidenceItem] = []
    summaries: list[GroupSummary] = []

    for group in groups:
        summaries.append(
            GroupSummary(
                document_id=group.document_id,
                section_root=group.section_root,
                candidate_count=group.size,
            )
        )
        for candidate in group.candidates:
            content = content_lookup.get(candidate.chunk_id, "")
            if not content:
                logger.warning(
                    "No content found for chunk %s; evidence item will have empty content",
                    candidate.chunk_id,
                )
            evidence.append(
                EvidenceItem(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    rank=candidate.rank,
                    content=content,
                    chunk_type=candidate.chunk_type,
                    source_ref=candidate.source_ref,
                    locator=candidate.locator,
                    match_signals=candidate.match_signals,
                    section_root=group.section_root,
                )
            )

    trace = PipelineTrace(
        total_candidates=total_candidates,
        group_count=len(groups),
        group_summaries=tuple(summaries),
    )

    # Sort evidence globally by rank so consumers can iterate as-ranked
    # without needing to re-sort across groups.
    evidence.sort(key=lambda e: e.rank)

    return EvidencePack(
        query=query,
        constraints_summary=_constraints_to_summary(constraints),
        evidence=evidence,
        trace=trace,
    )


def retrieve_evidence(
    raw_query: str,
    *,
    db_path: Path | None = None,
    top_k: int = 10,
) -> EvidencePack:
    """Full pipeline: raw query string → evidence pack.

    Runs normalization → lexical retrieval → shaping → evidence pack
    assembly in one call.
    """
    from .candidate_shaping import shape_candidates
    from .filters import build_constraints
    from .lexical_retriever import DEFAULT_DB_PATH, retrieve_lexical
    from .query_normalization import normalize_query

    norm_payload = normalize_query(raw_query)
    query = NormalizedQuery.from_query_normalization(norm_payload)
    constraints = build_constraints()
    effective_db = db_path or DEFAULT_DB_PATH

    candidates = retrieve_lexical(
        query, constraints=constraints, db_path=effective_db, top_k=top_k
    )
    groups = shape_candidates(candidates)

    chunk_ids = [
        candidate.chunk_id
        for group in groups
        for candidate in group.candidates
    ]
    content_lookup = _fetch_content(effective_db, chunk_ids)

    return build_evidence_pack(
        query,
        groups,
        constraints=constraints,
        content_lookup=content_lookup,
        total_candidates=len(candidates),
    )
