"""Tests for the answer-stage support assessor (§3.2)."""
from __future__ import annotations

from scripts.answer.support_assessor import assess_support
from scripts.retrieval.contracts import MatchSignals, NormalizedQuery
from scripts.retrieval.evidence_pack import (
    EvidenceItem,
    EvidencePack,
    PipelineTrace,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_query(raw: str = "attack of opportunity") -> NormalizedQuery:
    return NormalizedQuery(
        raw_query=raw,
        normalized_text=raw,
        tokens=raw.split(),
        protected_phrases=[],
        aliases_applied=[],
    )


def _make_signals(
    *,
    exact: list[str] | None = None,
    protected: list[str] | None = None,
    section_path_hit: bool = False,
    token_overlap_count: int = 0,
) -> MatchSignals:
    return {
        "exact_phrase_hits": list(exact or []),
        "protected_phrase_hits": list(protected or []),
        "section_path_hit": section_path_hit,
        "token_overlap_count": token_overlap_count,
    }


def _make_item(signals: MatchSignals, *, chunk_id: str = "chunk::001") -> EvidenceItem:
    return EvidenceItem(
        chunk_id=chunk_id,
        document_id="doc::test",
        rank=1,
        content="Top item content.",
        chunk_type="rule_section",
        source_ref={
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        locator={"section_path": ["Combat"], "source_location": "test"},
        match_signals=signals,
        section_root="Combat",
    )


def _make_pack(items: list[EvidenceItem]) -> EvidencePack:
    return EvidencePack(
        query=_make_query(),
        constraints_summary={},
        evidence=tuple(items),
        trace=PipelineTrace(
            total_candidates=len(items),
            group_count=0,
            group_summaries=(),
        ),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_empty_evidence_abstains():
    pack = _make_pack([])
    result = assess_support(pack)
    assert result.outcome == "abstain"
    assert result.trigger_code == "empty_evidence"


def test_exact_phrase_hit_grounded():
    item = _make_item(_make_signals(exact=["foo"]))
    result = assess_support(_make_pack([item]))
    assert result.outcome == "grounded"
    assert result.trigger_code is None


def test_protected_phrase_hit_grounded():
    item = _make_item(_make_signals(protected=["bar"]))
    result = assess_support(_make_pack([item]))
    assert result.outcome == "grounded"
    assert result.trigger_code is None


def test_section_path_hit_alone_grounded():
    item = _make_item(_make_signals(section_path_hit=True))
    result = assess_support(_make_pack([item]))
    assert result.outcome == "grounded"
    assert result.trigger_code is None


def test_token_overlap_alone_abstains():
    item = _make_item(_make_signals(token_overlap_count=5))
    result = assess_support(_make_pack([item]))
    assert result.outcome == "abstain"
    assert result.trigger_code == "weak_signals"


def test_zero_signals_abstains():
    item = _make_item(_make_signals())
    result = assess_support(_make_pack([item]))
    assert result.outcome == "abstain"
    assert result.trigger_code == "weak_signals"
