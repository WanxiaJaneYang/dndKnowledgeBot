"""Tests for pre-retrieval hard filters (Issue #32)."""
from __future__ import annotations

import pytest
import yaml
from pathlib import Path

from scripts.retrieval.filters import (
    apply_filters,
    build_constraints,
    load_filter_config,
    RetrievalConstraints,
    FilterResult,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


# ── Config loading ───────────────────────────────────────────────

def test_load_default_config():
    config = load_filter_config()
    assert "editions" in config
    assert "source_types" in config
    assert "authority_levels" in config
    assert "excluded_source_ids" in config


def test_default_config_has_35e():
    config = load_filter_config()
    assert "3.5e" in config["editions"]


def test_default_config_values_match_yaml():
    """Default config must stay in sync with the checked-in YAML."""
    config_path = REPO_ROOT / "configs" / "retrieval_filters.yaml"
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    config = load_filter_config()
    assert config == raw


# ── Constraints construction ─────────────────────────────────────

def test_build_constraints_from_default():
    c = build_constraints()
    assert isinstance(c, RetrievalConstraints)
    assert "3.5e" in c.editions
    assert "srd" in c.source_types


def test_build_constraints_from_custom_dict():
    c = build_constraints({
        "editions": ["5e"],
        "source_types": ["core_rulebook"],
        "authority_levels": ["official"],
        "excluded_source_ids": ["homebrew_1"],
    })
    assert c.editions == frozenset(["5e"])
    assert "homebrew_1" in c.excluded_source_ids


# ── Accepts / rejects ───────────────────────────────────────────

@pytest.fixture
def default_constraints():
    return build_constraints()


def _make_source_ref(edition="3.5e", source_type="srd", authority="official_reference", source_id="srd_35"):
    """Build a source_ref dict matching the real schema shape."""
    return {
        "source_id": source_id,
        "title": "System Reference Document",
        "edition": edition,
        "source_type": source_type,
        "authority_level": authority,
    }


def _chunk(edition="3.5e", source_type="srd", authority="official_reference", source_id="srd_35"):
    """Build a realistic chunk matching data/chunks/srd_35/*.json shape."""
    return {
        "chunk_id": f"chunk::{source_id}::test::001",
        "document_id": f"{source_id}::test::001",
        "source_ref": _make_source_ref(edition, source_type, authority, source_id),
        "locator": {"section_path": ["Test"], "source_location": "Test.rtf#001"},
        "chunk_type": "generic",
        "content": "Test content.",
    }


def _flat_meta(edition="3.5e", source_type="srd", authority="official_reference", source_id="srd_35"):
    """Build a flat metadata dict (no source_ref nesting) for fallback tests."""
    return {
        "edition": edition,
        "source_type": source_type,
        "authority_level": authority,
        "source_id": source_id,
    }


def test_accepts_valid_35e_srd(default_constraints):
    assert default_constraints.accepts(_chunk()) is True


def test_rejects_wrong_edition(default_constraints):
    assert default_constraints.accepts(_chunk(edition="5e")) is False


def test_rejects_wrong_source_type(default_constraints):
    assert default_constraints.accepts(_chunk(source_type="curated_commentary")) is False


def test_rejects_wrong_authority(default_constraints):
    assert default_constraints.accepts(_chunk(authority="fan_content")) is False


def test_rejects_excluded_source_id():
    c = build_constraints({
        "editions": ["3.5e"],
        "source_types": ["srd"],
        "authority_levels": ["official_reference"],
        "excluded_source_ids": ["srd_35"],
    })
    assert c.accepts(_chunk()) is False


def test_rejection_reason_edition(default_constraints):
    reason = default_constraints.rejection_reason(_chunk(edition="4e"))
    assert reason is not None
    assert "edition" in reason


def test_rejection_reason_none_when_accepted(default_constraints):
    assert default_constraints.rejection_reason(_chunk()) is None


# ── apply_filters integration ────────────────────────────────────

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
    candidates = [
        _chunk(),
        _chunk(edition="5e"),
    ]
    result = apply_filters(candidates)
    assert 1 in result.rejection_reasons
    assert "edition" in result.rejection_reasons[1]


def test_apply_filters_empty_when_all_rejected():
    candidates = [_chunk(edition="5e")]
    result = apply_filters(candidates)
    assert result.empty is True


def test_apply_filters_not_empty_when_some_accepted():
    candidates = [_chunk()]
    result = apply_filters(candidates)
    assert result.empty is False


def test_apply_filters_with_flat_metadata():
    """Flat dicts without source_ref still work via fallback."""
    candidates = [_flat_meta(), _flat_meta(edition="5e")]
    result = apply_filters(candidates)
    assert len(result.accepted) == 1
    assert len(result.rejected) == 1


def test_apply_filters_empty_candidates():
    result = apply_filters([])
    assert result.accepted == []
    assert result.rejected == []
    assert result.empty is True


# ── Real corpus chunk ────────────────────────────────────────────

def test_accepts_real_corpus_chunk(default_constraints):
    """A chunk shaped exactly like data/chunks/srd_35/*.json must pass."""
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


# ── Config-driven: only 3.5e passes by default ──────────────────

@pytest.mark.parametrize("edition", ["3e", "4e", "5e", "5.1e", "2e"])
def test_non_35e_editions_rejected_by_default(default_constraints, edition):
    assert default_constraints.accepts(_chunk(edition=edition)) is False


@pytest.mark.parametrize("source_type", [
    "core_rulebook", "supplement_rulebook", "errata_document", "faq_document", "srd",
])
def test_admitted_source_types_pass(default_constraints, source_type):
    assert default_constraints.accepts(_chunk(source_type=source_type)) is True


@pytest.mark.parametrize("source_type", ["curated_commentary", "personal_note"])
def test_non_admitted_source_types_rejected(default_constraints, source_type):
    assert default_constraints.accepts(_chunk(source_type=source_type)) is False
