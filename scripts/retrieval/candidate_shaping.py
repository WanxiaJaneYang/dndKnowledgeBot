"""Post-retrieval candidate shaping: group raw lexical hits by section.

Sits between retrieve_lexical() and the future evidence pack / consolidation
layer.  Groups candidates by their section root (first element of section_path
from the locator) so downstream consumers can reason about coverage per source
section rather than a flat ranked list.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import LexicalCandidate


@dataclass
class CandidateGroup:
    """A cluster of related candidates sharing a section root."""

    section_root: str
    candidates: list[LexicalCandidate]
    best_rank: int

    @property
    def size(self) -> int:
        return len(self.candidates)


def shape_candidates(
    candidates: list[LexicalCandidate],
) -> list[CandidateGroup]:
    """Group ranked candidates by section root.

    Returns groups sorted by the best (lowest) rank in each group.
    Candidates within each group preserve their original rank order.
    """
    if not candidates:
        return []

    groups_by_root: dict[str, list[LexicalCandidate]] = {}
    for candidate in candidates:
        root = _section_root(candidate)
        groups_by_root.setdefault(root, []).append(candidate)

    result: list[CandidateGroup] = []
    for root, members in groups_by_root.items():
        members.sort(key=lambda c: c.rank)
        group = CandidateGroup(
            section_root=root,
            candidates=members,
            best_rank=members[0].rank,
        )
        result.append(group)

    result.sort(key=lambda g: g.best_rank)
    return result


def _section_root(candidate: LexicalCandidate) -> str:
    """Extract the section root from a candidate's locator."""
    section_path = candidate.locator.get("section_path") or []
    if section_path:
        return section_path[0]
    return ""
