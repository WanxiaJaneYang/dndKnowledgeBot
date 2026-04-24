"""Contracts for the rule-based answer stage.

Defines the frozen dataclasses produced and consumed by the answer pipeline:
``AssessmentResult`` from the support assessor, ``AnswerSegment`` and
``Citation`` from the composer/binder, and the ``AnswerResult`` union
(``GroundedAnswer`` or ``Abstention``) returned by ``build_answer``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class AnswerSegment:
    """An ordered answer segment with its support type and citation ids."""

    segment_id: str
    text: str
    support_type: Literal["direct_support", "supported_inference"]
    citation_ids: tuple[str, ...]


@dataclass(frozen=True)
class Citation:
    """A chunk-level citation referenced by one or more segments."""

    citation_id: str
    chunk_id: str
    source_ref: dict[str, Any]
    locator: dict[str, Any]
    excerpt: str


@dataclass(frozen=True)
class GroundedAnswer:
    """A grounded answer: one primary plus up to two supporting segments."""

    query: str
    segments: tuple[AnswerSegment, ...]
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class Abstention:
    """An abstention with a canned human-readable reason and a trigger code."""

    query: str
    reason: str
    trigger_code: Literal["empty_evidence", "weak_signals"]


AnswerResult = GroundedAnswer | Abstention


@dataclass(frozen=True)
class AssessmentResult:
    """Outcome of the support assessor."""

    outcome: Literal["grounded", "abstain"]
    trigger_code: Literal["empty_evidence", "weak_signals"] | None
