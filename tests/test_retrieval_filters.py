"""Tests for pre-retrieval hard filters (Issue #32)."""
from __future__ import annotations

import pytest

from scripts.retrieval.filters import (
    apply_filters,
    build_constraints,
    RetrievalConstraints,
)


def _make_source_ref(edition="3.5e", source_type="srd", authority="official_reference", source_id="srd_35"):
    return {
        "source_id": source_id,
        "title": "System Reference Document",
        "edition": edition,
        "source_type": source_type,
        "authority_level": authority,
    }


def _chunk(edition="3.5e", source_type="srd", authority="official_reference", source_id="srd_35"):
    return {
        "chunk_id": f"chunk::{source_id}::test::001",
        "document_id": f"{source_id}::test::001",
        "source_ref": _make_source_ref(edition, source_type, authority, source_id),
        "locator": {"section_path": ["Test"], "source_location": "Test.rtf#001"},
        "chunk_type": "generic",
        "content": "Test content.",
    }


def _flat_meta(edition="3.5e", source_type="srd", authority="official_reference", source_id="srd_35"):
    return {
        "edition": edition,
        "source_type": source_type,
        "authority_level": authority,
        "source_id": source_id,
    }


def test_build_constraints_from_registry():
    c = build_constraints()
    assert isinstance(c, RetrievalConstraints)
    assert "3.5e" in c.editions
    assert "srd" in c.source_types
    assert "official_reference" in c.authority_levels


def test_build_constraints_skips_planned_later():
    c = build_constraints()
    assert "core_rulebook" not in c.source_types
    assert "official" not in c.authority_levels


def test_build_constraints_excluded_source_ids():
    c = build_constraints(excluded_source_ids=frozenset(["srd_35"]))
    assert "srd_35" in c.excluded_source_ids


def test_build_constraints_rejects_empty_registry(tmp_path):
    bad = tmp_path / "empty.yaml"
    bad.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        build_constraints(registry_path=bad)


def test_build_constraints_rejects_non_list_sources(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("sources: not_a_list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a list"):
        build_constraints(registry_path=bad)


@pytest.fixture
def default_constraints():
    return build_constraints()


def test_accepts_valid_35e_srd(default_constraints):
    assert default_constraints.accepts(_chunk()) is True


def test_rejects_wrong_edition(default_constraints):
    assert default_constraints.accepts(_chunk(edition="5e")) is False


def test_rejects_wrong_source_type(default_constraints):
    assert default_constraints.accepts(_chunk(source_type="curated_commentary")) is False


def test_rejects_wrong_authority(default_constraints):
    assert default_constraints.accepts(_chunk(authority="fan_content")) is False


def test_rejects_excluded_source_id():
    c = build_constraints(excluded_source_ids=frozenset(["srd_35"]))
    assert c.accepts(_chunk()) is False


def test_rejection_reason_edition(default_constraints):
    reason = default_constraints.rejection_reason(_chunk(edition="4e"))
    assert reason is not None
    assert "edition" in reason


def test_rejection_reason_none_when_accepted(default_constraints):
    assert default_constraints.rejection_reason(_chunk()) is None


def test_apply_filters_separates_accepted_and_rejected():
    candidates = [
        _chunk(),
        _chunk(edition="5e"),
        _chunk(source_type="personal_note"),
    ]
    result = apply_filters(candidates)
    assert len(result.accepted) == 1
    assert len(result.rejected) == 2
    assert result.constraints is not None


def test_apply_filters_records_rejection_reasons():
    candidates = [_chunk(), _chunk(edition="5e")]
    result = apply_filters(candidates)
    assert 1 in result.rejection_reasons
    assert "edition" in result.rejection_reasons[1]


def test_apply_filters_empty_when_all_rejected():
    result = apply_filters([_chunk(edition="5e")])
    assert result.empty is True


def test_apply_filters_not_empty_when_some_accepted():
    result = apply_filters([_chunk()])
    assert result.empty is False


def test_apply_filters_with_flat_metadata():
    candidates = [_flat_meta(), _flat_meta(edition="5e")]
    result = apply_filters(candidates)
    assert len(result.accepted) == 1
    assert len(result.rejected) == 1


def test_apply_filters_empty_candidates():
    result = apply_filters([])
    assert result.accepted == []
    assert result.rejected == []
    assert result.empty is True


def test_accepts_real_corpus_chunk(default_constraints):
    real_chunk = {
        "chunk_id": "chunk::srd_35::abilitiesandconditions::001_abilitiesandconditions",
        "document_id": "srd_35::abilitiesandconditions::001_abilitiesandconditions",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["AbilitiesandConditions", "AbilitiesandConditions"],
            "source_location": "AbilitiesandConditions.rtf#001_abilitiesandconditions",
        },
        "chunk_type": "generic",
        "content": "This material is Open Game Content.",
        "chunk_version": "v1-section-passthrough",
        "next_chunk_id": "chunk::srd_35::abilitiesandconditions::002_special_abilities",
    }
    assert default_constraints.accepts(real_chunk) is True
    assert default_constraints.rejection_reason(real_chunk) is None


@pytest.mark.parametrize("edition", ["3e", "4e", "5e", "5.1e", "2e"])
def test_non_35e_editions_rejected_by_default(default_constraints, edition):
    assert default_constraints.accepts(_chunk(edition=edition)) is False


@pytest.mark.parametrize("source_type", ["curated_commentary", "personal_note", "core_rulebook"])
def test_non_admitted_source_types_rejected(default_constraints, source_type):
    assert default_constraints.accepts(_chunk(source_type=source_type)) is False
