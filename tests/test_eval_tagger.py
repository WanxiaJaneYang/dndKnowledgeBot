"""Tests for ``scripts.eval.tagger``."""
from __future__ import annotations

from scripts.answer.contracts import (
    Abstention,
    AnswerSegment,
    Citation,
    GroundedAnswer,
)
from scripts.eval.contracts import GoldCase
from scripts.eval.tagger import tag_case
from scripts.retrieval.contracts import NormalizedQuery
from scripts.retrieval.evidence_pack import EvidencePack, PipelineTrace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pack(query: str = "attack of opportunity") -> EvidencePack:
    norm = NormalizedQuery(
        raw_query=query,
        normalized_text=query,
        tokens=query.split(),
        protected_phrases=[],
        aliases_applied=[],
    )
    return EvidencePack(
        query=norm,
        constraints_summary={},
        evidence=(),
        trace=PipelineTrace(total_candidates=0, group_count=0, group_summaries=()),
    )


def _make_case(
    *,
    eval_id: str = "P1-T-001",
    question: str = "When does a character provoke an attack of opportunity?",
    expected_source_ids: tuple[str, ...] = ("srd_35",),
    expected_section_or_entry: tuple[str, ...] = (
        "Combat: Attacks of Opportunity",
        "Movement",
    ),
    expected_behavior: str = "direct_answer",
) -> GoldCase:
    return GoldCase(
        eval_id=eval_id,
        question=question,
        question_type="direct_lookup",
        expected_source_ids=expected_source_ids,
        expected_section_or_entry=expected_section_or_entry,
        expected_behavior=expected_behavior,  # type: ignore[arg-type]
        expected_answer_notes="",
    )


def _make_citation(
    citation_id: str = "cit_1",
    *,
    source_id: str = "srd_35",
    edition: str = "3.5e",
    section_path: tuple[str, ...] = (
        "Combat: Attacks of Opportunity",
        "Movement",
    ),
    entry_title: str | None = None,
    excerpt: str = (
        "A character provokes an attack of opportunity when leaving a "
        "threatened square through movement."
    ),
) -> Citation:
    return Citation(
        citation_id=citation_id,
        chunk_id=f"chunk::{citation_id}",
        source_ref={
            "source_id": source_id,
            "title": "System Reference Document",
            "edition": edition,
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        locator={
            "section_path": list(section_path),
            **({"entry_title": entry_title} if entry_title else {}),
        },
        excerpt=excerpt,
    )


def _make_grounded(
    citations: tuple[Citation, ...],
    *,
    primary_support_type: str = "direct_support",
) -> GroundedAnswer:
    cit_ids = tuple(c.citation_id for c in citations)
    seg = AnswerSegment(
        segment_id="seg_1",
        text="primary excerpt",
        support_type=primary_support_type,  # type: ignore[arg-type]
        citation_ids=cit_ids,
    )
    return GroundedAnswer(
        query="q", segments=(seg,), citations=citations
    )


# ---------------------------------------------------------------------------
# Per-tag tests
# ---------------------------------------------------------------------------


def test_retrieval_miss_grounded_with_wrong_source():
    case = _make_case()
    cit = _make_citation(source_id="other_book")
    result = _make_grounded((cit,))
    tags, _ = tag_case(case, result, _make_pack())
    assert "retrieval_miss" in tags


def test_wrong_section_takes_precedence_over_wrong_entry():
    case = _make_case()
    # Right source, but section_path is in a totally different area.
    cit = _make_citation(
        section_path=("Spells", "Magic Missile"),
    )
    result = _make_grounded((cit,))
    tags, _ = tag_case(case, result, _make_pack())
    assert "wrong_section" in tags
    assert "wrong_entry" not in tags


def test_wrong_entry_when_section_root_matches_but_tail_does_not():
    case = _make_case()
    # Right section root ("Combat: Attacks of Opportunity") but a different entry.
    cit = _make_citation(
        section_path=("Combat: Attacks of Opportunity", "Threatened Squares"),
    )
    result = _make_grounded((cit,))
    tags, _ = tag_case(case, result, _make_pack())
    assert "wrong_entry" in tags
    assert "wrong_section" not in tags


def test_citation_mismatch_fires_independently_with_other_tags():
    case = _make_case(question="When does a character provoke movement attacks?")
    # Wrong source (retrieval_miss) AND excerpt has no overlap with question.
    cit = _make_citation(
        source_id="other_book",
        excerpt="Fireball deals 1d6 fire damage per caster level.",
    )
    result = _make_grounded((cit,))
    tags, checks = tag_case(case, result, _make_pack())
    assert "retrieval_miss" in tags
    assert "citation_mismatch" in tags
    assert checks[0].citation_mismatch is True


def test_unsupported_inference_fires_when_expected_direct():
    case = _make_case(expected_behavior="direct_answer")
    cit = _make_citation()
    result = _make_grounded((cit,), primary_support_type="supported_inference")
    tags, _ = tag_case(case, result, _make_pack())
    assert "unsupported_inference" in tags


def test_unsupported_inference_does_not_fire_when_expected_supported():
    case = _make_case(expected_behavior="supported_inference")
    cit = _make_citation()
    result = _make_grounded((cit,), primary_support_type="supported_inference")
    tags, _ = tag_case(case, result, _make_pack())
    assert "unsupported_inference" not in tags


def test_missing_abstain_when_grounded_but_should_abstain():
    case = _make_case(
        expected_source_ids=(),
        expected_section_or_entry=(),
        expected_behavior="abstain",
    )
    cit = _make_citation()
    result = _make_grounded((cit,))
    tags, _ = tag_case(case, result, _make_pack())
    assert "missing_abstain" in tags


def test_unnecessary_abstain_when_abstained_but_should_ground():
    case = _make_case()
    result = Abstention(
        query="q",
        reason="Insufficient evidence: no chunks retrieved for this query.",
        trigger_code="empty_evidence",
    )
    tags, _ = tag_case(case, result, _make_pack())
    assert "unnecessary_abstain" in tags


def test_edition_boundary_failure_when_wrong_edition_cited():
    case = _make_case()
    cit = _make_citation(edition="5e")
    result = _make_grounded((cit,))
    tags, _ = tag_case(case, result, _make_pack())
    assert "edition_boundary_failure" in tags


def test_empty_expected_section_short_circuits_section_and_entry_tags():
    # Abstain-shaped gold case but the model produced grounded — only the
    # behavior-mismatch and citation-content tags should be considered;
    # section/entry must NOT fire and the per-citation matches are None.
    case = _make_case(
        expected_source_ids=(),
        expected_section_or_entry=(),
        expected_behavior="abstain",
    )
    cit = _make_citation()
    result = _make_grounded((cit,))
    tags, checks = tag_case(case, result, _make_pack())
    assert "wrong_section" not in tags
    assert "wrong_entry" not in tags
    for c in checks:
        assert c.section_match is None
        assert c.entry_match is None


def test_clean_case_emits_no_tags():
    case = _make_case()
    cit = _make_citation()  # right source, section, entry, edition, overlap
    result = _make_grounded((cit,))
    tags, _ = tag_case(case, result, _make_pack())
    assert tags == ()
