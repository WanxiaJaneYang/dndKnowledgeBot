"""Tests for evidence-pack contract (issue #35 + #34 adjacent-chunk work)."""
from __future__ import annotations

from scripts.retrieval.candidate_consolidation import (
    EvidenceSpan,
    SpanGroup,
    consolidate_adjacent,
)
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
    *,
    section_path: list[str] | None = None,
    previous_chunk_id: str | None = None,
    next_chunk_id: str | None = None,
    parent_chunk_id: str | None = None,
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
        parent_chunk_id=parent_chunk_id,
        previous_chunk_id=previous_chunk_id,
        next_chunk_id=next_chunk_id,
    )


def _make_span_group(
    section_root: str,
    candidates: list[LexicalCandidate],
    document_id: str = "doc::test",
) -> SpanGroup:
    """Build a CandidateGroup, then run real consolidation over it.

    This matches how the production pipeline produces SpanGroups so tests
    don't hand-craft a shape the code never generates.
    """
    group = CandidateGroup(
        document_id=document_id,
        section_root=section_root,
        candidates=candidates,
        best_rank=candidates[0].rank if candidates else 0,
    )
    return consolidate_adjacent([group])[0]


# ---------------------------------------------------------------------------
# build_evidence_pack — singleton-only inputs
# ---------------------------------------------------------------------------


def test_build_evidence_pack_basic():
    query = _make_query()
    c1 = _make_candidate("chunk::001", "doc::001", rank=1)
    c2 = _make_candidate("chunk::002", "doc::001", rank=2)
    # Two candidates with no adjacency links → two singleton spans.
    group = _make_span_group("Combat", [c1, c2], document_id="doc::001")

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
    group = _make_span_group("Combat", [c1], document_id="doc::combat")

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
    group_combat = _make_span_group("Combat", [c1, c2], document_id="doc::combat")
    group_spells = _make_span_group("Spells", [c3], document_id="doc::spells")

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
    combat_summary = pack.trace.group_summaries[0]
    assert combat_summary.document_id == "doc::combat"
    assert combat_summary.section_root == "Combat"
    assert combat_summary.candidate_count == 2  # two candidates entered
    assert combat_summary.span_count == 2  # both became singleton spans
    assert pack.trace.group_summaries[1].candidate_count == 1
    assert pack.trace.group_summaries[1].span_count == 1


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
    group = _make_span_group("Combat", [c1], document_id="doc::001")

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
    group = _make_span_group("Combat", [c], document_id="doc::sig")

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
    c_combat = _make_candidate("chunk::002", "doc::combat", rank=2)
    c_spells = _make_candidate("chunk::001", "doc::spells", rank=1)
    group_combat = _make_span_group("Combat", [c_combat], document_id="doc::combat")
    group_spells = _make_span_group("Spells", [c_spells], document_id="doc::spells")

    pack = build_evidence_pack(
        query,
        [group_combat, group_spells],
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
    group = _make_span_group("Combat", [c], document_id="doc::001")

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
# Span metadata propagation (#34 adjacent-chunk work)
# ---------------------------------------------------------------------------


def test_singleton_span_metadata_on_evidence_item():
    """A singleton span produces an EvidenceItem whose span fields describe
    just the one chunk, with merge_reason='singleton'."""
    query = _make_query()
    c = _make_candidate("chunk::A", "doc::combat", rank=1)
    group = _make_span_group("Combat", [c], document_id="doc::combat")

    pack = build_evidence_pack(
        query,
        [group],
        constraints=_DEFAULT_CONSTRAINTS,
        content_lookup={"chunk::A": "solo"},
        total_candidates=1,
    )

    item = pack.evidence[0]
    assert item.chunk_ids == ("chunk::A",)
    assert item.start_chunk_id == "chunk::A"
    assert item.end_chunk_id == "chunk::A"
    assert item.merge_reason == "singleton"


def test_adjacent_span_metadata_on_evidence_item():
    """A multi-chunk span surfaces chunk_ids in reading order; start/end
    describe the span range; representative's content is carried as the
    item's content (no concatenation)."""
    query = _make_query()
    # A→B→C, same section_path, B is the best-ranked (representative).
    a = _make_candidate(
        "chunk::A", "doc::combat", rank=3, next_chunk_id="chunk::B"
    )
    b = _make_candidate(
        "chunk::B",
        "doc::combat",
        rank=1,
        previous_chunk_id="chunk::A",
        next_chunk_id="chunk::C",
    )
    c = _make_candidate(
        "chunk::C", "doc::combat", rank=2, previous_chunk_id="chunk::B"
    )
    group = _make_span_group("Combat", [a, b, c], document_id="doc::combat")

    content_lookup = {
        "chunk::A": "prelude",
        "chunk::B": "core rule",
        "chunk::C": "coda",
    }
    pack = build_evidence_pack(
        query,
        [group],
        constraints=_DEFAULT_CONSTRAINTS,
        content_lookup=content_lookup,
        total_candidates=3,
    )

    assert len(pack.evidence) == 1
    item = pack.evidence[0]
    assert item.chunk_id == "chunk::B"  # representative = best-ranked
    assert item.content == "core rule"  # representative's content only
    assert item.chunk_ids == ("chunk::A", "chunk::B", "chunk::C")
    assert item.start_chunk_id == "chunk::A"  # reading order
    assert item.end_chunk_id == "chunk::C"
    assert item.merge_reason == "adjacent_span"


def test_adjacency_passthrough_on_evidence_item():
    """Representative's parent/previous/next chunk ids surface on the item."""
    query = _make_query()
    c = _make_candidate(
        "chunk::001",
        "doc::001",
        rank=1,
        parent_chunk_id="chunk::parent",
        previous_chunk_id="chunk::prev",
        next_chunk_id="chunk::next",
    )
    group = _make_span_group("Combat", [c], document_id="doc::001")

    pack = build_evidence_pack(
        query,
        [group],
        constraints=_DEFAULT_CONSTRAINTS,
        content_lookup={"chunk::001": "content"},
        total_candidates=1,
    )

    item = pack.evidence[0]
    assert item.parent_chunk_id == "chunk::parent"
    assert item.previous_chunk_id == "chunk::prev"
    assert item.next_chunk_id == "chunk::next"


def test_span_count_reflects_consolidation_collapse():
    """When 3 candidates collapse into 1 adjacent span, GroupSummary should
    report candidate_count=3 and span_count=1."""
    query = _make_query()
    a = _make_candidate(
        "chunk::A", "doc::combat", rank=1, next_chunk_id="chunk::B"
    )
    b = _make_candidate(
        "chunk::B",
        "doc::combat",
        rank=2,
        previous_chunk_id="chunk::A",
        next_chunk_id="chunk::C",
    )
    c = _make_candidate(
        "chunk::C", "doc::combat", rank=3, previous_chunk_id="chunk::B"
    )
    group = _make_span_group("Combat", [a, b, c], document_id="doc::combat")

    pack = build_evidence_pack(
        query,
        [group],
        constraints=_DEFAULT_CONSTRAINTS,
        content_lookup={},
        total_candidates=3,
    )

    summary = pack.trace.group_summaries[0]
    assert summary.candidate_count == 3
    assert summary.span_count == 1


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
    # Singleton span by default since only one chunk is indexed.
    assert item.merge_reason == "singleton"
    assert item.chunk_ids == (chunk["chunk_id"],)

    assert pack.trace.total_candidates == 1
    assert pack.trace.group_count == 1
    assert pack.trace.group_summaries[0].candidate_count == 1
    assert pack.trace.group_summaries[0].span_count == 1

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


def test_retrieve_evidence_merges_adjacent_hits(tmp_path):
    """End-to-end: two adjacent chunks that both match collapse into one
    adjacent_span EvidenceItem."""
    import json as _json

    from scripts.retrieval.evidence_pack import retrieve_evidence
    from scripts.retrieval.lexical_index import build_chunk_index

    base = {
        "document_id": "srd_35::combat",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "chunk_type": "rule_section",
    }
    a = {
        **base,
        "chunk_id": "chunk::srd_35::combat::001_a",
        "locator": {
            "section_path": ["Combat", "Attack of Opportunity"],
            "source_location": "Combat.rtf#001",
        },
        "content": "Attack of opportunity first half — the trigger conditions.",
        "next_chunk_id": "chunk::srd_35::combat::002_b",
    }
    b = {
        **base,
        "chunk_id": "chunk::srd_35::combat::002_b",
        "locator": {
            "section_path": ["Combat", "Attack of Opportunity"],
            "source_location": "Combat.rtf#002",
        },
        "content": "Attack of opportunity second half — the damage resolution.",
        "previous_chunk_id": "chunk::srd_35::combat::001_a",
    }
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    path_a.write_text(_json.dumps(a), encoding="utf-8")
    path_b.write_text(_json.dumps(b), encoding="utf-8")
    db_path = tmp_path / "retrieval.db"
    build_chunk_index(db_path, [path_a, path_b])

    pack = retrieve_evidence("attack of opportunity", db_path=db_path, top_k=5)

    # Two candidates matched → consolidated to one span.
    assert pack.trace.total_candidates == 2
    assert pack.trace.group_count == 1
    assert pack.trace.group_summaries[0].candidate_count == 2
    assert pack.trace.group_summaries[0].span_count == 1

    assert len(pack.evidence) == 1
    item = pack.evidence[0]
    assert item.merge_reason == "adjacent_span"
    assert set(item.chunk_ids) == {a["chunk_id"], b["chunk_id"]}


# ---------------------------------------------------------------------------
# Public export
# ---------------------------------------------------------------------------


def test_evidence_pack_importable_from_package():
    from scripts.retrieval import (
        EvidenceItem as EI,
        EvidencePack as EP,
        EvidenceSpan as ES,
        GroupSummary as GS,
        PipelineTrace as PT,
        SpanGroup as SG,
        build_evidence_pack as bep,
        consolidate_adjacent as cons,
        retrieve_evidence as re_,
    )
    assert bep is build_evidence_pack
    assert EI is EvidenceItem
    assert EP is EvidencePack
    assert ES is EvidenceSpan
    assert GS is GroupSummary
    assert PT is PipelineTrace
    assert SG is SpanGroup
    assert cons is consolidate_adjacent
