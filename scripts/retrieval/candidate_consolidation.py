"""Post-shaping candidate consolidation: reduce overlap within groups.

Operates on CandidateGroup objects from shape_candidates().  Reduces
overlap-heavy candidate sets so the same evidence is not counted multiple
times in the evidence pack.

Phase 1 consolidation rules (applied per group):
1. Same-document dedup: if multiple candidates come from the same
   document_id, keep only the highest-ranked one and record the others
   as merged.

Provenance is preserved: ConsolidatedCandidate tracks all merged chunk_ids
and the reason for merging, so debug/inspection can show what was dropped.
"""
from __future__ import annotations

from dataclasses import dataclass

from .candidate_shaping import CandidateGroup
from .contracts import LexicalCandidate


@dataclass
class ConsolidatedCandidate:
    """A candidate that may represent one or more original candidates."""

    representative: LexicalCandidate
    merged_chunk_ids: list[str]
    merge_reason: str

    @property
    def chunk_id(self) -> str:
        return self.representative.chunk_id

    @property
    def rank(self) -> int:
        return self.representative.rank


@dataclass
class ConsolidatedGroup:
    """A CandidateGroup after consolidation."""

    section_root: str
    candidates: list[ConsolidatedCandidate]
    dropped_count: int = 0

    @property
    def size(self) -> int:
        return len(self.candidates)


def consolidate_group(group: CandidateGroup) -> ConsolidatedGroup:
    """Consolidate a single candidate group by collapsing same-document duplicates.

    The first-seen candidate per document_id becomes the representative,
    so candidates must be rank-ordered (ascending).  We sort defensively
    rather than relying on the upstream contract.
    """
    seen: dict[str, ConsolidatedCandidate] = {}

    for candidate in sorted(group.candidates, key=lambda c: c.rank):
        doc_id = candidate.document_id
        if doc_id not in seen:
            seen[doc_id] = ConsolidatedCandidate(
                representative=candidate,
                merged_chunk_ids=[candidate.chunk_id],
                merge_reason="unique",
            )
        else:
            seen[doc_id].merged_chunk_ids.append(candidate.chunk_id)
            seen[doc_id].merge_reason = "same_document"

    consolidated = sorted(seen.values(), key=lambda c: c.rank)
    dropped = len(group.candidates) - len(consolidated)

    return ConsolidatedGroup(
        section_root=group.section_root,
        candidates=consolidated,
        dropped_count=dropped,
    )


def consolidate_candidates(
    groups: list[CandidateGroup],
) -> list[ConsolidatedGroup]:
    """Consolidate all candidate groups.

    Returns consolidated groups in the same order as the input.
    """
    return [consolidate_group(g) for g in groups]
