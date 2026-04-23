"""Tests for ``build_answer`` and the strict/debug JSON serializers."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

from scripts.answer.composer import compose_segments
from scripts.answer.contracts import Abstention, GroundedAnswer
from scripts.answer.pipeline import build_answer, to_debug_json, to_strict_json
from scripts.retrieval.contracts import MatchSignals, NormalizedQuery
from scripts.retrieval.evidence_pack import (
    EvidenceItem,
    EvidencePack,
    GroupSummary,
    PipelineTrace,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMAS_DIR = _REPO_ROOT / "schemas"

_SOURCE_REF = {
    "source_id": "srd_35",
    "title": "System Reference Document",
    "edition": "3.5e",
    "source_type": "srd",
    "authority_level": "official_reference",
}


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
        source_ref=_SOURCE_REF,
        locator={"section_path": [section_root, "X"], "source_location": "t"},
        match_signals=signals or _make_signals(exact=["q"]),
        section_root=section_root,
    )


def _make_pack(
    items: list[EvidenceItem],
    *,
    raw_query: str = "attack of opportunity",
) -> EvidencePack:
    group_summaries = tuple(
        GroupSummary(
            document_id=item.document_id,
            section_root=item.section_root,
            candidate_count=1,
        )
        for item in items
    )
    return EvidencePack(
        query=_make_query(raw_query),
        constraints_summary={},
        evidence=tuple(items),
        trace=PipelineTrace(
            total_candidates=len(items),
            group_count=len(group_summaries),
            group_summaries=group_summaries,
        ),
    )


def _make_validator() -> Draft7Validator:
    main = json.loads(
        (_SCHEMAS_DIR / "answer_with_citations.schema.json").read_text(encoding="utf-8")
    )
    common = json.loads(
        (_SCHEMAS_DIR / "common.schema.json").read_text(encoding="utf-8")
    )
    common_resource = Resource.from_contents(common, default_specification=DRAFT7)
    registry = Registry().with_resources(
        [
            ("./common.schema.json", common_resource),
            ("common.schema.json", common_resource),
        ]
    )
    return Draft7Validator(main, registry=registry)


# ---------------------------------------------------------------------------
# build_answer — outcome dispatch
# ---------------------------------------------------------------------------


def test_empty_pack_returns_abstention_with_canned_reason():
    pack = _make_pack([])
    result = build_answer(pack)
    assert isinstance(result, Abstention)
    assert result.trigger_code == "empty_evidence"
    assert result.reason == "Insufficient evidence: no chunks retrieved for this query."


def test_weak_signals_returns_abstention_with_canned_reason():
    weak = _make_item("c1", rank=1, signals=_make_signals(token_overlap_count=5))
    result = build_answer(_make_pack([weak]))
    assert isinstance(result, Abstention)
    assert result.trigger_code == "weak_signals"
    assert (
        result.reason
        == "Insufficient evidence: retrieved chunks do not clearly match the query."
    )


def test_grounded_with_sibling_and_cross_section_produces_three_segments():
    primary = _make_item("c1", rank=1, signals=_make_signals(exact=["A"]))
    sibling = _make_item("c2", rank=2, signals=_make_signals(exact=["A"]))
    cross = _make_item(
        "c3",
        rank=3,
        document_id="doc::other",
        section_root="Spells",
        signals=_make_signals(exact=["B"]),
    )
    pack = _make_pack([primary, sibling, cross])
    result = build_answer(pack)
    assert isinstance(result, GroundedAnswer)
    assert len(result.segments) == 3
    assert len(result.citations) == 3
    assert result.query == pack.query.raw_query


# ---------------------------------------------------------------------------
# Strict JSON — schema validation
# ---------------------------------------------------------------------------


def test_strict_json_grounded_validates_against_schema():
    primary = _make_item("c1", rank=1, signals=_make_signals(exact=["A"]))
    cross = _make_item(
        "c2",
        rank=2,
        document_id="doc::other",
        section_root="Spells",
        signals=_make_signals(exact=["B"]),
    )
    pack = _make_pack([primary, cross])
    result = build_answer(pack)

    payload = to_strict_json(result, pack)
    _make_validator().validate(payload)

    assert payload["answer_type"] == "grounded"
    assert payload["retrieval_metadata"]["candidate_chunks"] == 2
    assert payload["retrieval_metadata"]["selected_chunks"] == 2


def test_strict_json_abstain_validates_against_schema():
    pack = _make_pack([])
    result = build_answer(pack)
    payload = to_strict_json(result, pack)
    _make_validator().validate(payload)
    assert payload["answer_type"] == "abstain"
    assert (
        payload["abstention_reason"]
        == "Insufficient evidence: no chunks retrieved for this query."
    )


# ---------------------------------------------------------------------------
# Debug JSON — strict shape after popping `debug`
# ---------------------------------------------------------------------------


def test_debug_json_grounded_strict_shape_after_pop():
    primary = _make_item("c1", rank=1, signals=_make_signals(exact=["A"]))
    sibling = _make_item("c2", rank=2, signals=_make_signals(exact=["A"]))
    pack = _make_pack([primary, sibling])
    result = build_answer(pack)
    composed = compose_segments(pack)

    payload = to_debug_json(result, pack, composed)
    debug = payload.pop("debug")
    _make_validator().validate(payload)

    assert set(debug.keys()) == {"abstention_code", "pipeline_trace", "selected_items"}
    assert debug["abstention_code"] is None
    assert len(debug["selected_items"]) == len(composed)
    for entry in debug["selected_items"]:
        assert set(entry.keys()) >= {"chunk_id", "rank", "match_signals", "role"}


def test_debug_json_abstain_has_code_and_empty_selected_items():
    pack = _make_pack([])
    result = build_answer(pack)
    payload = to_debug_json(result, pack, ())
    debug = payload.pop("debug")
    _make_validator().validate(payload)

    assert debug["abstention_code"] == "empty_evidence"
    assert debug["selected_items"] == []
