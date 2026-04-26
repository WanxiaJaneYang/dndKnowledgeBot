"""Failure-tag classifier for one (case, result, pack) triple."""
from __future__ import annotations

from scripts.answer.contracts import AnswerResult, GroundedAnswer
from scripts.retrieval.evidence_pack import EvidencePack

from .contracts import CitationCheck, GoldCase
from .matching import (
    entry_matches,
    extract_expected_head,
    extract_expected_tail,
    section_root_matches,
    tokenize,
)


# Tag order matches spec §3.2. Reports group failing cases in this order.
_TAG_ORDER: tuple[str, ...] = (
    "retrieval_miss",
    "wrong_section",
    "wrong_entry",
    "citation_mismatch",
    "unsupported_inference",
    "missing_abstain",
    "unnecessary_abstain",
    "edition_boundary_failure",
)


def tag_case(
    case: GoldCase,
    result: AnswerResult,
    pack: EvidencePack,  # noqa: ARG001 — kept for parity with spec signature
) -> tuple[tuple[str, ...], tuple[CitationCheck, ...]]:
    """Compute the failure-tag tuple and per-citation checks for one case."""
    tags: set[str] = set()
    checks: list[CitationCheck] = []

    is_grounded = isinstance(result, GroundedAnswer)
    is_abstain_expected = case.expected_behavior == "abstain"

    # Behavior-class mismatches.
    if not is_grounded and not is_abstain_expected:
        tags.add("unnecessary_abstain")
    if is_grounded and is_abstain_expected:
        tags.add("missing_abstain")

    if not is_grounded:
        # No citations to check; return early with empty checks.
        return _ordered_tags(tags), ()

    grounded: GroundedAnswer = result  # type: ignore[assignment]
    citations = grounded.citations
    expected_sources = set(case.expected_source_ids)
    has_section_expectation = bool(case.expected_section_or_entry)
    expected_head = (
        extract_expected_head(case.expected_section_or_entry)
        if has_section_expectation
        else None
    )
    expected_tail = (
        extract_expected_tail(case.expected_section_or_entry)
        if has_section_expectation
        else None
    )
    question_tokens = tokenize(case.question)

    any_source_match = False
    any_section_match = False
    any_entry_match = False
    any_citation_mismatch = False
    any_edition_failure = False

    for citation in citations:
        source_id = citation.source_ref.get("source_id", "")
        edition = citation.source_ref.get("edition", "")
        section_path = tuple(citation.locator.get("section_path", []) or [])
        entry_title = citation.locator.get("entry_title")
        excerpt_tokens = tokenize(citation.excerpt or "")
        shared = tuple(sorted(question_tokens & excerpt_tokens))

        source_match = bool(expected_sources) and source_id in expected_sources
        edition_match = edition == "3.5e"
        if not edition_match:
            any_edition_failure = True

        if has_section_expectation and expected_head is not None:
            sec_match: bool | None = section_root_matches(section_path, expected_head)
        else:
            sec_match = None
        if has_section_expectation and expected_tail is not None:
            ent_match: bool | None = entry_matches(
                section_path, entry_title, expected_tail
            )
        else:
            ent_match = None

        cm = len(shared) == 0
        if cm:
            any_citation_mismatch = True

        if source_match:
            any_source_match = True
        if sec_match:
            any_section_match = True
        if ent_match:
            any_entry_match = True

        checks.append(
            CitationCheck(
                citation_id=citation.citation_id,
                source_match=source_match,
                section_match=sec_match,
                entry_match=ent_match,
                edition_match=edition_match,
                token_overlap=shared,
                citation_mismatch=cm,
            )
        )

    # retrieval_miss only fires when expected_source_ids is non-empty
    # (abstain-expected cases carry an empty list and never trigger this).
    if (
        expected_sources
        and citations
        and not any_source_match
    ):
        tags.add("retrieval_miss")

    if has_section_expectation and citations:
        # wrong_section / wrong_entry are mutually exclusive: when sections
        # are wrong we report only the more specific tag (spec §3.3).
        if not any_section_match:
            tags.add("wrong_section")
        elif not any_entry_match:
            tags.add("wrong_entry")

    if any_citation_mismatch:
        tags.add("citation_mismatch")

    if any_edition_failure:
        tags.add("edition_boundary_failure")

    # unsupported_inference fires only when the gold expects a direct answer
    # but the primary segment is a supported_inference.
    if (
        case.expected_behavior == "direct_answer"
        and grounded.segments
        and grounded.segments[0].support_type == "supported_inference"
    ):
        tags.add("unsupported_inference")

    return _ordered_tags(tags), tuple(checks)


def _ordered_tags(tags: set[str]) -> tuple[str, ...]:
    """Return tags in canonical §3.2 order."""
    return tuple(t for t in _TAG_ORDER if t in tags)
