"""Phase 1 gold-set evaluation harness."""
from __future__ import annotations

from .contracts import (
    ActualSummary,
    CaseOutcome,
    CitationCheck,
    CitationSummary,
    EvalReport,
    GoldCase,
)
from .loader import load_gold_set
from .runner import run_case
from .tagger import tag_case

__all__ = [
    "ActualSummary",
    "CaseOutcome",
    "CitationCheck",
    "CitationSummary",
    "EvalReport",
    "GoldCase",
    "load_gold_set",
    "run_case",
    "tag_case",
]
