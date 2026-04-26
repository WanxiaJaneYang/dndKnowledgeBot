"""Rule-based answer stage: EvidencePack → AnswerResult."""
from __future__ import annotations

from .citation_binder import bind_citations
from .composer import compose_segments, compose_segments_with_decisions
from .contracts import (
    Abstention,
    AnswerResult,
    AnswerSegment,
    AssessmentResult,
    Citation,
    GroundedAnswer,
    SlotDecision,
)
from .pipeline import build_answer
from .support_assessor import assess_support

__all__ = [
    "Abstention",
    "AnswerResult",
    "AnswerSegment",
    "AssessmentResult",
    "Citation",
    "GroundedAnswer",
    "SlotDecision",
    "assess_support",
    "bind_citations",
    "build_answer",
    "compose_segments",
    "compose_segments_with_decisions",
]
