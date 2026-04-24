"""Rule-based answer stage: EvidencePack → AnswerResult."""
from __future__ import annotations

from .citation_binder import bind_citations
from .composer import compose_segments
from .contracts import (
    Abstention,
    AnswerResult,
    AnswerSegment,
    AssessmentResult,
    Citation,
    GroundedAnswer,
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
    "assess_support",
    "bind_citations",
    "build_answer",
    "compose_segments",
]
