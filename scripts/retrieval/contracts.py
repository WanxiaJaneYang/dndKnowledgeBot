"""Contracts for lexical retrieval."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedQuery:
    """Typed retrieval-facing query contract."""

    raw_query: str
    normalized_text: str
    tokens: list[str]
    protected_phrases: list[str]
    aliases_applied: list[dict[str, str]]

    @classmethod
    def from_query_normalization(cls, payload: dict[str, Any]) -> "NormalizedQuery":
        """Adapt the existing Issue #31 dict shape into a typed contract."""
        return cls(
            raw_query=payload["original_query"],
            normalized_text=payload["normalized_text"],
            tokens=list(payload["tokens"]),
            protected_phrases=list(payload["protected_phrases"]),
            aliases_applied=list(payload["alias_expansions"]),
        )


@dataclass(frozen=True)
class LexicalCandidate:
    """Stable candidate output for lexical retrieval."""

    chunk_id: str
    document_id: str
    rank: int
    raw_score: float
    score_direction: str
    chunk_type: str
    source_ref: dict[str, Any]
    locator: dict[str, Any]
    match_signals: dict[str, Any]
