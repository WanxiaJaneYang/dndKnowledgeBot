from __future__ import annotations

from scripts.answer.composer import compose_segments_with_decisions
from scripts.answer.contracts import Citation
from scripts.retrieval.contracts import LexicalCandidate, MatchSignals, NormalizedQuery
from scripts.retrieval.evidence_pack import EvidenceItem, EvidencePack, PipelineTrace
from scripts.ui.panels import (
    format_answer_segments,
    format_candidate_rows,
    format_citation_rows,
    format_slot_decision_rows,
)


def _make_query() -> NormalizedQuery:
    return NormalizedQuery(
        raw_query="attack of opportunity",
        normalized_text="attack of opportunity",
        tokens=["attack", "of", "opportunity"],
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


def _make_item(
    chunk_id: str,
    *,
    rank: int,
    document_id: str = "doc::main",
    section_root: str = "Combat",
    content: str = "Rule text.",
    signals: MatchSignals | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        chunk_id=chunk_id,
        document_id=document_id,
        rank=rank,
        content=content,
        chunk_type="rule_section",
        source_ref={
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        locator={"section_path": [section_root], "source_location": "test"},
        match_signals=signals or _make_signals(exact=["attack"]),
        section_root=section_root,
        chunk_ids=(chunk_id,),
        start_chunk_id=chunk_id,
        end_chunk_id=chunk_id,
        merge_reason="singleton",
        parent_chunk_id=None,
        previous_chunk_id=None,
        next_chunk_id=None,
    )


def _make_pack(items: list[EvidenceItem]) -> EvidencePack:
    return EvidencePack(
        query=_make_query(),
        constraints_summary={
            "editions": ["3.5e"],
            "source_types": ["srd"],
            "authority_levels": ["official_reference"],
            "excluded_source_ids": [],
        },
        evidence=tuple(items),
        trace=PipelineTrace(
            total_candidates=len(items),
            group_count=0,
            group_summaries=(),
        ),
    )


def test_format_answer_segments_includes_markers():
    rows = format_answer_segments(
        [
            {
                "segment_id": "seg_1",
                "text": "Attacks of opportunity happen when a foe drops its guard.",
                "support_type": "direct_support",
                "citation_ids": ("cit_1", "cit_2"),
            }
        ]
    )

    assert rows == [
        {
            "segment_id": "seg_1",
            "support_type": "direct_support",
            "citations": "[cit_1] [cit_2]",
            "text": "Attacks of opportunity happen when a foe drops its guard.",
        }
    ]


def test_format_slot_decision_rows_flattens_rejected_candidates():
    primary = _make_item("c1", rank=1, signals=_make_signals(exact=["A", "B"]))
    sibling = _make_item("c2", rank=2)
    cross_subset = _make_item(
        "c3",
        rank=3,
        document_id="doc::other",
        section_root="Spells",
        signals=_make_signals(exact=["A"]),
    )
    segments, decisions = compose_segments_with_decisions(_make_pack([primary, sibling, cross_subset]))

    rows = format_slot_decision_rows(decisions)

    assert segments[0].segment_id == "seg_1"
    assert rows[0]["slot"] == "primary"
    assert rows[2]["slot"] == "cross-section"
    assert "c3:hit_set_subset_of_primary" in rows[2]["rejected"]
    assert rows[3]["reason"] == "no_fallback_sibling_available"


def test_format_candidate_rows_exposes_rank_section_and_signals():
    item = _make_item(
        "c1",
        rank=1,
        section_root="Combat",
        signals=_make_signals(exact=["attack"], protected=["opportunity"], token_overlap_count=3),
    )

    rows = format_candidate_rows((item,))

    assert rows == [
        {
            "rank": 1,
            "chunk_id": "c1",
            "document_id": "doc::main",
            "section_root": "Combat",
            "chunk_type": "rule_section",
            "match_signals": "exact=['attack']; protected=['opportunity']; token_overlap=3",
        }
    ]


def test_format_candidate_rows_uses_locator_when_candidate_has_no_section_root():
    item = LexicalCandidate(
        chunk_id="c1",
        document_id="doc::main",
        rank=1,
        raw_score=0.25,
        score_direction="lower_is_better",
        chunk_type="rule_section",
        source_ref={
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        locator={
            "section_path": ["Combat", "Attacks of Opportunity"],
            "source_location": "test",
        },
        match_signals=_make_signals(
            exact=["attack of opportunity"],
            protected=["attack of opportunity"],
            token_overlap_count=3,
        ),
    )

    rows = format_candidate_rows((item,))

    assert rows == [
        {
            "rank": 1,
            "chunk_id": "c1",
            "document_id": "doc::main",
            "section_root": "Combat",
            "chunk_type": "rule_section",
            "match_signals": (
                "exact=['attack of opportunity']; "
                "protected=['attack of opportunity']; token_overlap=3"
            ),
        }
    ]


def test_format_citation_rows_extracts_title_and_locator():
    citation = Citation(
        citation_id="cit_1",
        chunk_id="c1",
        source_ref={
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        locator={"section_path": ["Combat", "Attacks of Opportunity"], "source_location": "test"},
        excerpt="Rule excerpt.",
    )

    rows = format_citation_rows((citation,))

    assert rows == [
        {
            "citation_id": "cit_1",
            "chunk_id": "c1",
            "title": "System Reference Document",
            "locator": "Combat > Attacks of Opportunity | test",
            "excerpt": "Rule excerpt.",
        }
    ]
