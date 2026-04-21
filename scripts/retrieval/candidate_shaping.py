"""Post-retrieval candidate shaping: group raw lexical hits by section.

Sits between retrieve_lexical() and the future evidence pack / consolidation
layer.  Groups candidates by (document_id, section_root) so downstream
consumers can reason about coverage per source section rather than a flat
ranked list.  Using a composite key prevents unrelated sections from
different documents or sources from being merged just because they share
a top-level heading name (e.g. two different sources both called "Combat").
"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import LexicalCandidate


@dataclass
class CandidateGroup:
    """A cluster of related candidates sharing a document and section root."""

    document_id: str
    section_root: str
    candidates: list[LexicalCandidate]
    best_rank: int

    @property
    def size(self) -> int:
        return len(self.candidates)


def shape_candidates(
    candidates: list[LexicalCandidate],
) -> list[CandidateGroup]:
    """Group ranked candidates by (document_id, section_root).

    Returns groups sorted by the best (lowest) rank in each group.
    Candidates within each group preserve their original rank order.
    """
    if not candidates:
        return []

    groups: dict[tuple[str, str], list[LexicalCandidate]] = {}
    for candidate in candidates:
        key = _group_key(candidate)
        groups.setdefault(key, []).append(candidate)

    result: list[CandidateGroup] = []
    for (doc_id, root), members in groups.items():
        members.sort(key=lambda c: c.rank)
        group = CandidateGroup(
            document_id=doc_id,
            section_root=root,
            candidates=members,
            best_rank=members[0].rank,
        )
        result.append(group)

    result.sort(key=lambda g: g.best_rank)
    return result


def _group_key(candidate: LexicalCandidate) -> tuple[str, str]:
    """Composite group key: (document_id, section_root)."""
    section_path = candidate.locator.get("section_path") or []
    root = section_path[0] if section_path else ""
    return (candidate.document_id, root)
