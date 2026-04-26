"""Frozen dataclasses for the Phase 1 gold-set eval harness."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


_ExpectedBehavior = Literal[
    "direct_answer", "supported_inference", "narrow_answer", "abstain"
]


@dataclass(frozen=True)
class GoldCase:
    """One case in the Phase 1 gold set."""

    eval_id: str
    question: str
    question_type: str
    expected_source_ids: tuple[str, ...]
    expected_section_or_entry: tuple[str, ...]
    expected_behavior: _ExpectedBehavior
    expected_answer_notes: str


@dataclass(frozen=True)
class CitationSummary:
    """Compact view of one citation, suitable for the report."""

    citation_id: str
    chunk_id: str
    source_id: str
    edition: str
    section_path: tuple[str, ...]
    entry_title: str | None


@dataclass(frozen=True)
class CitationCheck:
    """Per-citation comparison against the gold case's expectations.

    section_match and entry_match are None when expected_section_or_entry
    is empty (the matchers have nothing to compare against).
    """

    citation_id: str
    source_match: bool
    section_match: bool | None
    entry_match: bool | None
    edition_match: bool
    token_overlap: tuple[str, ...]
    citation_mismatch: bool


@dataclass(frozen=True)
class ActualSummary:
    """Compact view of the actual answer produced for a case."""

    primary_excerpt: str | None
    primary_support_type: str | None
    citations: tuple[CitationSummary, ...]
    abstention_reason: str | None


@dataclass(frozen=True)
class CaseOutcome:
    """One case's result: tags, summaries, diagnostics."""

    eval_id: str
    question: str
    question_type: str
    expected_behavior: _ExpectedBehavior
    actual_answer_type: Literal["grounded", "abstain"]
    tags: tuple[str, ...]
    actual_summary: ActualSummary
    citation_checks: tuple[CitationCheck, ...]
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class EvalReport:
    """The full report produced by one run over the gold set."""

    dataset_id: str
    run_started_at: str
    case_count: int
    tag_counts: dict[str, int]
    behavior_match_rate: float
    cases: tuple[CaseOutcome, ...]
