"""Adjacent-chunk consolidation: collapse reading-order-contiguous hits into spans.

Sits between shape_candidates() and build_evidence_pack().  Within each
CandidateGroup, walks adjacency links (next_chunk_id / previous_chunk_id)
to identify runs of retrieval hits that are contiguous in the source
document, and emits one EvidenceSpan per run.

Scope (deliberately narrow — Phase 1):
- **Retrieval-hit consolidation only.**  We merge chunks that *are both in
  the hit set* and are adjacent in reading order.  We do **not** bridge
  gaps: if chunks A and C are hit but B (between them) is not, the output
  is two singleton spans, not one 3-chunk span.  Whether to fetch B as
  supporting context is an answer-side decision, not a retrieval-side one.
- **No content concatenation.**  A span's representative carries the
  content used for answer generation; the other chunk_ids in the span are
  metadata.  Concatenating span text is an answer-context-assembly
  concern, deferred.
- **Heading-boundary refusal.**  Spans are constrained to a single
  section_path (full path equality, not just section_root).  Two hits in
  the same section_root but different sub-sections stay as separate
  singletons even if adjacency links connect them.

Non-goals (explicit):
- near-duplicate collapse (tracked in #68 as an ADR-only follow-up)
- same-document dedup (delivered structurally by the composite
  CandidateGroup key in #64)
- content-based similarity or semantic merging
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .candidate_shaping import CandidateGroup
from .contracts import LexicalCandidate


MergeReason = Literal["singleton", "adjacent_span"]


@dataclass(frozen=True)
class EvidenceSpan:
    """A run of retrieval hits contiguous in reading order.

    Invariants:
    - ``chunk_ids`` is in reading order (earliest → latest in the source
      document), *not* in rank order.  ``chunk_ids[0] == start_chunk_id``
      and ``chunk_ids[-1] == end_chunk_id``.
    - ``representative`` is the best-ranked (lowest ``rank``) chunk in the
      span.  It is *not* guaranteed to equal ``start_chunk_id`` or
      ``end_chunk_id`` — the highest-signal chunk can sit anywhere inside
      the span.
    - A singleton span has ``len(chunk_ids) == 1`` and
      ``merge_reason == "singleton"``; a multi-chunk span has
      ``merge_reason == "adjacent_span"``.
    """

    representative: LexicalCandidate
    chunk_ids: tuple[str, ...]
    start_chunk_id: str
    end_chunk_id: str
    merge_reason: MergeReason


@dataclass(frozen=True)
class SpanGroup:
    """A CandidateGroup after adjacent-chunk consolidation."""

    document_id: str
    section_root: str
    spans: tuple[EvidenceSpan, ...]

    @property
    def span_count(self) -> int:
        return len(self.spans)


def consolidate_adjacent(groups: list[CandidateGroup]) -> list[SpanGroup]:
    """Consolidate each CandidateGroup into reading-order spans.

    Preserves group order and identity — one CandidateGroup in, one
    SpanGroup out, same document_id and section_root.

    Spans within a group are sorted by the representative's rank
    (best-ranked span first).
    """
    return [_consolidate_group(group) for group in groups]


def _consolidate_group(group: CandidateGroup) -> SpanGroup:
    by_id: dict[str, LexicalCandidate] = {c.chunk_id: c for c in group.candidates}
    visited: set[str] = set()
    spans: list[EvidenceSpan] = []

    # Walk chains starting from "heads" — candidates whose predecessor is
    # not in the hit set (or has a different section_path). This guarantees
    # each candidate is visited exactly once even if the candidate list is
    # not pre-sorted by reading order.
    for candidate in group.candidates:
        if candidate.chunk_id in visited:
            continue
        if not _is_chain_head(candidate, by_id):
            continue
        chain = _walk_chain(candidate, by_id, visited)
        spans.append(_make_span(chain))

    # Defensive: catch any unvisited candidates caused by broken
    # adjacency data (e.g. cycles). Emit each as a singleton rather than
    # dropping silently.
    for candidate in group.candidates:
        if candidate.chunk_id not in visited:
            visited.add(candidate.chunk_id)
            spans.append(_make_span([candidate]))

    spans.sort(key=lambda s: s.representative.rank)
    return SpanGroup(
        document_id=group.document_id,
        section_root=group.section_root,
        spans=tuple(spans),
    )


def _is_chain_head(
    candidate: LexicalCandidate,
    by_id: dict[str, LexicalCandidate],
) -> bool:
    """A candidate is a chain head if its predecessor is not a merge partner.

    The predecessor is a merge partner iff it is in the hit set (``by_id``)
    *and* shares the same section_path.
    """
    prev_id = candidate.previous_chunk_id
    if prev_id is None or prev_id not in by_id:
        return True
    predecessor = by_id[prev_id]
    return _section_path(predecessor) != _section_path(candidate)


def _walk_chain(
    head: LexicalCandidate,
    by_id: dict[str, LexicalCandidate],
    visited: set[str],
) -> list[LexicalCandidate]:
    """Walk forward via next_chunk_id, collecting the chain in reading order."""
    chain: list[LexicalCandidate] = [head]
    visited.add(head.chunk_id)
    current = head

    while True:
        next_id = current.next_chunk_id
        if next_id is None or next_id not in by_id:
            break
        if next_id in visited:  # cycle guard
            break
        nxt = by_id[next_id]
        if _section_path(nxt) != _section_path(current):
            break
        chain.append(nxt)
        visited.add(next_id)
        current = nxt

    return chain


def _make_span(chain: list[LexicalCandidate]) -> EvidenceSpan:
    representative = min(chain, key=lambda c: c.rank)
    merge_reason: MergeReason = "singleton" if len(chain) == 1 else "adjacent_span"
    return EvidenceSpan(
        representative=representative,
        chunk_ids=tuple(c.chunk_id for c in chain),
        start_chunk_id=chain[0].chunk_id,
        end_chunk_id=chain[-1].chunk_id,
        merge_reason=merge_reason,
    )


def _section_path(candidate: LexicalCandidate) -> tuple[str, ...]:
    path = candidate.locator.get("section_path") or []
    return tuple(path)
