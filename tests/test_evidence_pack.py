"""Tests for evidence-pack contract (issue #35)."""
from __future__ import annotations

from scripts.retrieval.candidate_shaping import CandidateGroup
from scripts.retrieval.contracts import LexicalCandidate, NormalizedQuery
from scripts.retrieval.evidence_pack import (
    EvidenceItem,
    EvidencePack,
    GroupSummary,
    PipelineTrace,
    build_evidence_pack,
)
from scripts.retrieval.filters import RetrievalConstraints


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_CONSTRAINTS = RetrievalConstraints(
    editions=frozenset({"3.5e"}),
    source_types=frozenset({"srd"}),
    authority_levels=frozenset({"official_reference"}),
    excluded_source_ids=frozenset(),
)


def _make_query(raw: str = "attack of opportunity") -> NormalizedQuery:
    return NormalizedQuery(
        raw_query=raw,
        normalized_text="attack of opportunity",
        tokens=["attack", "opportunity"],
        protected_phrases=["attack of opportunity"],
        aliases_applied=[],
    )


def _make_candidate(
    chunk_id: str,
    document_id: str,
    rank: int,
    section_path: list[str] | None = None,
) -> LexicalCandidate:
    return LexicalCandidate(
        chunk_id=chunk_id,
        document_id=document_id,
        rank=rank,
        raw_score=-1.0,
        score_direction="lower_is_better",
        chunk_type="subsection",
        source_ref={
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        locator={
            "section_path": section_path or ["Combat", "Test"],
            "source_location": "test",
        },
        match_signals={
            "exact_phrase_hits": [],
            "protected_phrase_hits": [],
            "section_path_hit": False,
            "token_overlap_count": 0,
        },
    )


def _make_group(
    section_root: str,
    candidates: list[LexicalCandidate],
    document_id: str = "doc::test",
) -> CandidateGroup:
    return CandidateGroup(
        document_id=document_id,
        section_root=section_root,
        candidates=candidates,
        best_rank=candidates[0].rank if candidates else 0,
    )


# ---------------------------------------------------------------------------
# build_evidence_pack
# ---------------------------------------------------------------------------


def test_build_evidence_pack_basic():
    query = _make_query()
    c1 = _make_candidate("chunk::001", "doc::001", rank=1)
    c2 = _make_candidate("chunk::002", "doc::001", rank=2)
    group = _make_group("Combat", [c1, c2], document_id="doc::001")

    content_lookup = {
        "chunk::001": "Attack of opportunity rules...",
        "chunk::002": "More AoO details...",
    }

    pack = build_evidence_pack(
        query,
        [group],
        constraints=_DEFAULT_CONSTRAINTS,
        content_lookup=content_lookup,
        total_candidates=2,
    )

    assert isinstance(pack, EvidencePack)
    assert pack.query is query
    assert len(pack.evidence) == 2
    assert pack.evidence[0].chunk_id == "chunk::001"
    assert pack.evidence[0].content == "Attack of opportunity rules..."
    assert pack.evidence[1].content == "More AoO details..."


def test_evidence_items_carry_section_root():
    query = _make_query()
    c1 = _make_candidate("chunk::001", "doc::combat", rank=1)
    group = _make_group("Combat", [c1], document_id="doc::combat")

    pack = build_evidence_pack(
        query,
        [group],
        constraints=_DEFAULT_CONSTRAINTS,
        content_lookup={"chunk::001": "content"},
        total_candidates=1,
    )

    assert len(pack.evidence) == 1
    assert pack.evidence[0].section_root == "Combat"


def test_pipeline_trace_counts():
    query = _make_query()
    c1 = _make_candidate("chunk::001", "doc::combat", rank=1)
    c2 = _make_candidate("chunk::002", "doc::combat", rank=2)
    c3 = _make_candidate("chunk::003", "doc::spells", rank=3)
    group_combat = _make_group("Combat", [c1, c2], document_id="doc::combat")
    group_spells = _make_group("Spells", [c3], document_id="doc::spells")

    pack = build_evidence_pack(
        query,
        [group_combat, group_spells],
        constraints=_DEFAULT_CONSTRAINTS,
        content_lookup={},
        total_candidates=3,
    )

    assert pack.trace.total_candidates == 3
    assert pack.trace.group_count == 2
    assert len(pack.trace.group_summaries) == 2
    assert pack.trace.group_summaries[0].document_id == "doc::combat"
    assert pack.trace.group_summaries[0].section_root == "Combat"
    assert pack.trace.group_summaries[0].candidate_count == 2
    assert pack.trace.group_summaries[1].candidate_count == 1


def test_constraints_summary():
    query = _make_query()
    pack = build_evidence_pack(
        query,
        [],
        constraints=_DEFAULT_CONSTRAINTS,
        content_lookup={},
        total_candidates=0,
    )

    assert pack.constraints_summary["editions"] == ["3.5e"]
    assert pack.constraints_summary["source_types"] == ["srd"]
    assert pack.constraints_summary["authority_levels"] == ["official_reference"]
    assert pack.constraints_summary["excluded_source_ids"] == []


def test_empty_groups():
    query = _make_query()
    pack = build_evidence_pack(
        query,
        [],
        constraints=_DEFAULT_CONSTRAINTS,
        content_lookup={},
        total_candidates=0,
    )

    assert len(pack.evidence) == 0
    assert pack.trace.total_candidates == 0
    assert pack.trace.group_count == 0
    assert pack.trace.group_summaries == ()


def test_missing_content_defaults_to_empty_string():
    query = _make_query()
    c1 = _make_candidate("chunk::001", "doc::001", rank=1)
    group = _make_group("Combat", [c1], document_id="doc::001")

    pack = build_evidence_pack(
        query,
        [group],
        constraints=_DEFAULT_CONSTRAINTS,
        content_lookup={},  # no content provided
        total_candidates=1,
    )

    assert pack.evidence[0].content == ""


def test_evidence_items_carry_match_signals():
    query = _make_query()
    c = LexicalCandidate(
        chunk_id="chunk::sig",
        document_id="doc::sig",
        rank=1,
        raw_score=-5.0,
        score_direction="lower_is_better",
        chunk_type="rule_section",
        source_ref={
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        locator={"section_path": ["Combat", "AoO"], "source_location": "test"},
        match_signals={
            "exact_phrase_hits": ["attack of opportunity"],
            "protected_phrase_hits": ["attack of opportunity"],
            "section_path_hit": True,
            "token_overlap_count": 2,
        },
    )
    group = _make_group("Combat", [c], document_id="doc::sig")

    pack = build_evidence_pack(
        query,
        [group],
        constraints=_DEFAULT_CONSTRAINTS,
        content_lookup={"chunk::sig": "AoO rules"},
        total_candidates=1,
    )

    item = pack.evidence[0]
    assert item.match_signals["section_path_hit"] is True
    assert item.match_signals["exact_phrase_hits"] == ["attack of opportunity"]
    assert item.chunk_type == "rule_section"


def test_evidence_sorted_globally_by_rank():
    """Evidence items from different groups are sorted by rank, not group order."""
    query = _make_query()
    # Group "Spells" has rank 1, group "Combat" has rank 2 — but pass Combat first
    c_combat = _make_candidate("chunk::002", "doc::combat", rank=2)
    c_spells = _make_candidate("chunk::001", "doc::spells", rank=1)
    group_combat = _make_group("Combat", [c_combat], document_id="doc::combat")
    group_spells = _make_group("Spells", [c_spells], document_id="doc::spells")

    pack = build_evidence_pack(
        query,
        [group_combat, group_spells],  # Combat first, but rank 2
        constraints=_DEFAULT_CONSTRAINTS,
        content_lookup={},
        total_candidates=2,
    )

    ranks = [e.rank for e in pack.evidence]
    assert ranks == [1, 2], f"Evidence should be globally rank-sorted, got {ranks}"


def test_source_ref_carries_title_for_citation():
    """source_ref must include title — required by answer_with_citations schema."""
    query = _make_query()
    c = _make_candidate("chunk::001", "doc::001", rank=1)
    group = _make_group("Combat", [c], document_id="doc::001")

    pack = build_evidence_pack(
        query,
        [group],
        constraints=_DEFAULT_CONSTRAINTS,
        content_lookup={"chunk::001": "content"},
        total_candidates=1,
    )

    assert "title" in pack.evidence[0].source_ref
    assert pack.evidence[0].source_ref["title"] == "System Reference Document"


# ---------------------------------------------------------------------------
# retrieve_evidence orchestrator
# ---------------------------------------------------------------------------


def test_retrieve_evidence_end_to_end(tmp_path):
    """End-to-end: raw query string → EvidencePack with hydrated content."""
    import json as _json

    from scripts.retrieval.evidence_pack import retrieve_evidence
    from scripts.retrieval.lexical_index import build_chunk_index

    chunk = {
        "chunk_id": "chunk::srd_35::combat::001_attack_of_opportunity",
        "document_id": "srd_35::combat",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["Combat", "Attack of Opportunity"],
            "source_location": "Combat.rtf#001",
        },
        "chunk_type": "rule_section",
        "content": "An attack of opportunity is a single melee attack.",
    }
    chunk_path = tmp_path / "aoo.json"
    chunk_path.write_text(_json.dumps(chunk), encoding="utf-8")
    db_path = tmp_path / "retrieval.db"
    build_chunk_index(db_path, [chunk_path])

    pack = retrieve_evidence("attack of opportunity", db_path=db_path, top_k=5)

    assert len(pack.evidence) == 1
    item = pack.evidence[0]
    assert item.chunk_id == chunk["chunk_id"]
    assert item.content == chunk["content"]
    assert item.section_root == "Combat"
    assert item.rank == 1

    assert pack.trace.total_candidates == 1
    assert pack.trace.group_count == 1
    assert pack.trace.group_summaries[0].candidate_count == 1

    # Query context threaded through.
    assert pack.query.raw_query == "attack of opportunity"


def test_retrieve_evidence_empty_for_no_match(tmp_path):
    """retrieve_evidence returns a pack with empty evidence when no chunks match."""
    import json as _json

    from scripts.retrieval.evidence_pack import retrieve_evidence
    from scripts.retrieval.lexical_index import build_chunk_index

    chunk = {
        "chunk_id": "chunk::srd_35::combat::001_attack_of_opportunity",
        "document_id": "srd_35::combat",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["Combat", "Attack of Opportunity"],
            "source_location": "Combat.rtf#001",
        },
        "chunk_type": "rule_section",
        "content": "An attack of opportunity is a single melee attack.",
    }
    chunk_path = tmp_path / "aoo.json"
    chunk_path.write_text(_json.dumps(chunk), encoding="utf-8")
    db_path = tmp_path / "retrieval.db"
    build_chunk_index(db_path, [chunk_path])

    pack = retrieve_evidence("psionics", db_path=db_path, top_k=5)

    assert pack.evidence == ()
    assert pack.trace.total_candidates == 0
    assert pack.trace.group_count == 0


# ---------------------------------------------------------------------------
# Public export
# ---------------------------------------------------------------------------


def test_evidence_pack_importable_from_package():
    from scripts.retrieval import (
        EvidenceItem as EI,
        EvidencePack as EP,
        GroupSummary as GS,
        PipelineTrace as PT,
        build_evidence_pack as bep,
        retrieve_evidence as re_,
    )
    assert bep is build_evidence_pack
    assert EI is EvidenceItem
    assert EP is EvidencePack
    assert GS is GroupSummary
    assert PT is PipelineTrace
