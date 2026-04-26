"""Tests for match-signal singular/plural normalization (issue #89)."""
from __future__ import annotations

from scripts.retrieval.contracts import NormalizedQuery
from scripts.retrieval.match_signals import (
    _singularize,
    _singularize_text,
    build_match_signals,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_query(
    *,
    normalized_text: str,
    tokens: list[str],
    protected_phrases: list[str] | None = None,
) -> NormalizedQuery:
    return NormalizedQuery(
        raw_query=normalized_text,
        normalized_text=normalized_text,
        tokens=tokens,
        protected_phrases=protected_phrases or [],
        aliases_applied=[],
    )


def _make_chunk(content: str) -> dict:
    return {
        "chunk_id": "chunk::srd_35::test::001",
        "document_id": "srd_35::test::001",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["Combat", "Test"],
            "source_location": "Combat.rtf#001_test",
        },
        "chunk_type": "rule_section",
        "content": content,
    }


# ---------------------------------------------------------------------------
# _singularize unit tests
# ---------------------------------------------------------------------------


def test_singularize_strips_trailing_s_for_simple_plurals() -> None:
    assert _singularize("attacks") == "attack"
    assert _singularize("feats") == "feat"
    assert _singularize("actions") == "action"


def test_singularize_handles_ies_plurals() -> None:
    assert _singularize("abilities") == "ability"
    assert _singularize("opportunities") == "opportunity"


def test_singularize_handles_es_plurals() -> None:
    assert _singularize("boxes") == "box"
    assert _singularize("matches") == "match"


def test_singularize_preserves_non_plural_exception_words() -> None:
    assert _singularize("class") == "class"
    assert _singularize("is") == "is"
    assert _singularize("us") == "us"
    assert _singularize("this") == "this"
    assert _singularize("process") == "process"


def test_singularize_leaves_words_without_plural_suffix_unchanged() -> None:
    assert _singularize("combat") == "combat"
    assert _singularize("attack") == "attack"
    assert _singularize("opportunity") == "opportunity"


def test_singularize_short_words_are_protected_by_length_guards() -> None:
    # "as" / "is" are in the exception list but the length guards are
    # defense in depth: any 2-char word ending in "s" should not be stripped.
    assert _singularize("as") == "as"
    assert _singularize("is") == "is"


def test_singularize_us_singulars_are_symmetric_with_their_plurals() -> None:
    """-us singular nouns must collapse symmetrically with their -uses
    plurals.  Without an explicit exception, the trailing-s rule strips
    `bonus -> bonu` while the -es rule turns `bonuses -> bonus`, leaving
    the two forms unmatched.  Common D&D rules vocabulary depends on this:
    bonus feat, skill focus, status condition, spell radius.
    """
    # bonus / bonuses
    assert _singularize("bonus") == "bonus"
    assert _singularize("bonuses") == "bonus"
    # focus / focuses
    assert _singularize("focus") == "focus"
    assert _singularize("focuses") == "focus"
    # status / statuses
    assert _singularize("status") == "status"
    assert _singularize("statuses") == "status"
    # radius — plural in rules text is usually just "radiuses" (irregular
    # "radii" is not handled by this naive singularizer; that is a known
    # limitation, not in scope for #89).
    assert _singularize("radius") == "radius"
    assert _singularize("radiuses") == "radius"
    # corpus / corpuses
    assert _singularize("corpus") == "corpus"
    assert _singularize("corpuses") == "corpus"


# ---------------------------------------------------------------------------
# _singularize_text unit tests
# ---------------------------------------------------------------------------


def test_singularize_text_preserves_non_word_characters() -> None:
    assert _singularize_text("attacks of opportunity") == "attack of opportunity"


def test_singularize_text_handles_punctuation_and_whitespace() -> None:
    assert (
        _singularize_text("combat: attacks, feats; abilities.")
        == "combat: attack, feat; ability."
    )


def test_singularize_text_is_idempotent() -> None:
    once = _singularize_text("attacks of opportunity")
    twice = _singularize_text(once)
    assert once == twice


# ---------------------------------------------------------------------------
# build_match_signals end-to-end
# ---------------------------------------------------------------------------


def test_singular_query_matches_plural_section_path() -> None:
    query = _make_query(
        normalized_text="attack of opportunity",
        tokens=["attack", "opportunity"],
        protected_phrases=["attack of opportunity"],
    )
    chunk = _make_chunk(
        "Sometimes a combatant lets her guard down and provokes such attacks."
    )

    signals = build_match_signals(
        query, chunk, "CombatI > ATTACKS OF OPPORTUNITY"
    )

    assert signals["section_path_hit"] is True
    assert signals["exact_phrase_hits"] == ["attack of opportunity"]
    assert signals["protected_phrase_hits"] == ["attack of opportunity"]


def test_plural_query_matches_singular_section_path() -> None:
    query = _make_query(
        normalized_text="attacks of opportunity",
        tokens=["attacks", "opportunity"],
        protected_phrases=["attacks of opportunity"],
    )
    chunk = _make_chunk("An attack of opportunity is a single melee attack.")

    signals = build_match_signals(
        query, chunk, "Combat > Attack of Opportunity"
    )

    assert signals["section_path_hit"] is True
    assert signals["exact_phrase_hits"] == ["attacks of opportunity"]
    assert signals["protected_phrase_hits"] == ["attacks of opportunity"]


def test_singular_query_singular_section_still_matches() -> None:
    query = _make_query(
        normalized_text="attack of opportunity",
        tokens=["attack", "opportunity"],
        protected_phrases=["attack of opportunity"],
    )
    chunk = _make_chunk("An attack of opportunity is a single melee attack.")

    signals = build_match_signals(
        query, chunk, "Combat > Attack of Opportunity"
    )

    assert signals["section_path_hit"] is True
    assert signals["exact_phrase_hits"] == ["attack of opportunity"]


def test_plural_query_plural_section_still_matches() -> None:
    query = _make_query(
        normalized_text="attacks of opportunity",
        tokens=["attacks", "opportunity"],
        protected_phrases=["attacks of opportunity"],
    )
    chunk = _make_chunk("These free attacks are called attacks of opportunity.")

    signals = build_match_signals(
        query, chunk, "CombatI > ATTACKS OF OPPORTUNITY"
    )

    assert signals["section_path_hit"] is True
    assert signals["exact_phrase_hits"] == ["attacks of opportunity"]


def test_token_overlap_counts_singular_plural_equivalents_once() -> None:
    query = _make_query(
        normalized_text="bonus feats",
        tokens=["bonus", "feats"],
    )
    chunk = _make_chunk(
        "A fighter gains a bonus feat at 1st level and additional feats later."
    )

    signals = build_match_signals(query, chunk, "Classes > Fighter")

    # "feats" -> "feat" both sides; "feat" present in haystack; counted once.
    assert signals["token_overlap_count"] == 2


def test_negative_singular_query_does_not_spuriously_match_unrelated_word() -> None:
    # "ability" should not match "Abilene" — the `_singularize` rules don't
    # touch "abilene" (doesn't end in s/es/ies) and the word-boundary regex
    # prevents substring hits.
    query = _make_query(
        normalized_text="ability",
        tokens=["ability"],
        protected_phrases=["ability"],
    )
    chunk = _make_chunk("The town of Abilene has nothing to do with D&D abilities.")

    signals = build_match_signals(query, chunk, "Geography > Abilene")

    # "abilities" in content singularizes to "ability" — that IS a real match.
    assert signals["exact_phrase_hits"] == ["ability"]
    # But "Abilene" must not contribute on its own.
    chunk_no_abilities = _make_chunk("The town of Abilene is unrelated to gaming.")
    signals_no_match = build_match_signals(
        query, chunk_no_abilities, "Geography > Abilene"
    )
    assert signals_no_match["exact_phrase_hits"] == []
    assert signals_no_match["protected_phrase_hits"] == []
    assert signals_no_match["section_path_hit"] is False


def test_singular_us_query_matches_plural_uses_section_path() -> None:
    """End-to-end check that the -us exception fix flows through
    build_match_signals: a singular `bonus` query must match a section
    path containing the plural `bonuses`, because both collapse to
    `bonus`.  Without the exception, `bonus` would singularize to `bonu`
    while `bonuses` would singularize to `bonus`, leaving them unmatched."""
    query = _make_query(
        normalized_text="bonus",
        tokens=["bonus"],
        protected_phrases=["bonus"],
    )
    chunk = _make_chunk(
        "Fighters receive bonuses to attack rolls when wielding favoured weapons."
    )

    signals = build_match_signals(query, chunk, "Combat > Bonuses")

    assert signals["section_path_hit"] is True
    assert signals["exact_phrase_hits"] == ["bonus"]
    assert signals["protected_phrase_hits"] == ["bonus"]
    assert signals["token_overlap_count"] >= 1


def test_class_exception_word_is_not_collapsed() -> None:
    # If "class" were collapsed to "clas", a query for "class" against a
    # section about "Class Skills" would still match — but it would also
    # spuriously match a hypothetical token "clas" anywhere. The exception
    # list keeps the matching predictable.
    query = _make_query(
        normalized_text="class",
        tokens=["class"],
        protected_phrases=["class"],
    )
    chunk = _make_chunk("Class skills are listed for each character class.")

    signals = build_match_signals(query, chunk, "Classes > Class Skills")

    # Both query and haystack tokens go through _singularize: "classes"
    # -> "class", "class" stays "class" (exception). The match works.
    assert signals["section_path_hit"] is True
    assert signals["exact_phrase_hits"] == ["class"]
