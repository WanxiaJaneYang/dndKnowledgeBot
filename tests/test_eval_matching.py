"""Tests for ``scripts.eval.matching``."""
from __future__ import annotations

from scripts.eval.matching import (
    entry_matches,
    extract_expected_head,
    extract_expected_tail,
    section_root_matches,
    tokenize,
)


# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------


def test_tokenize_lowercases_and_drops_stopwords():
    tokens = tokenize("What does the Magic Missile spell DO?")
    assert "magic" in tokens
    assert "missile" in tokens
    assert "spell" in tokens
    # stopwords removed
    for sw in ("what", "does", "the", "do"):
        assert sw not in tokens


def test_tokenize_keeps_alphanumerics_and_drops_punctuation():
    tokens = tokenize("DC 15 + spell-level rules!")
    assert "dc" in tokens
    assert "15" in tokens
    assert "spell" in tokens
    assert "level" in tokens
    assert "rules" in tokens
    # No punctuation tokens.
    assert all(t.isalnum() for t in tokens)


# ---------------------------------------------------------------------------
# extract_expected_head / extract_expected_tail
# ---------------------------------------------------------------------------


def test_extract_expected_head_drops_rtf_extension():
    # CombatI.rtf is filename-shaped → falls back to [1].
    head = extract_expected_head(("CombatI.rtf", "Run"))
    assert head == "run"


def test_extract_expected_head_falls_back_when_first_is_filename():
    head = extract_expected_head(("Races.rtf", "Races", "Humans"))
    assert head == "races"


def test_extract_expected_head_returns_first_when_only_one_element():
    # Only one element, even if filename-shaped: use as-is (substring match
    # in the matcher is generous enough).
    head = extract_expected_head(("CombatI.rtf",))
    assert head == "combati"


def test_extract_expected_head_returns_lowercased_section_root():
    head = extract_expected_head(("Combat: Attacks of Opportunity", "Movement"))
    assert head == "combat: attacks of opportunity"


def test_extract_expected_head_empty_returns_none():
    assert extract_expected_head(()) is None


def test_extract_expected_tail_returns_last_lowercased():
    tail = extract_expected_tail(("Combat: Movement", "5-Foot Step"))
    assert tail == "5-foot step"


def test_extract_expected_tail_empty_returns_none():
    assert extract_expected_tail(()) is None


# ---------------------------------------------------------------------------
# section_root_matches
# ---------------------------------------------------------------------------


def test_section_root_matches_substring():
    assert section_root_matches(("Combat", "Attack of Opportunity"), "combat")


def test_section_root_matches_colon_prefix():
    # Citation is "Combat: Attacks of Opportunity"; expected head is "combat".
    assert section_root_matches(
        ("Combat: Attacks of Opportunity",), "combat"
    )


def test_section_root_matches_negative():
    assert not section_root_matches(("Spells", "Magic Missile"), "combat")


# ---------------------------------------------------------------------------
# entry_matches
# ---------------------------------------------------------------------------


def test_entry_matches_against_section_path():
    assert entry_matches(
        ("Combat", "Attack of Opportunity", "Movement"),
        None,
        "movement",
    )


def test_entry_matches_against_entry_title():
    assert entry_matches(
        ("Combat", "Attack of Opportunity"),
        "Threatened Squares",
        "threatened",
    )


def test_entry_matches_negative():
    assert not entry_matches(
        ("Spells", "Magic Missile"), "Damage", "movement"
    )
