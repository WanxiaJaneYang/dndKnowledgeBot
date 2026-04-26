"""Match-signal helpers for lexical retrieval candidates."""
from __future__ import annotations

import re
from typing import Any

from .contracts import NormalizedQuery


# Words that end in -s/-es/-ies but are NOT plural; collapsing them
# would produce a different word.  -us singulars (bonus/focus/status/radius)
# are listed explicitly so the trailing-s rule does not strip them
# asymmetrically — without these entries `bonus -> bonu` while `bonuses -> bonus`,
# breaking singular/plural collapse for very common D&D rules vocabulary
# (bonus feat, skill focus, status condition, spell radius).
_PLURAL_EXCEPTIONS: frozenset[str] = frozenset({
    "as", "is", "us", "his", "this", "yes", "less",
    "class", "miss", "boss", "loss", "pass", "process",
    "bonus", "focus", "status", "radius", "corpus",
})


def build_match_signals(
    query: NormalizedQuery,
    chunk: dict[str, Any],
    section_path_text: str,
) -> dict[str, Any]:
    """Compute lightweight lexical match signals for a candidate chunk.

    Phrase hits (``exact_phrase_hits``, ``protected_phrase_hits``) and
    ``section_path_hit`` are computed after singular/plural normalization,
    so they are *morphology-normalized* phrase hits — not necessarily
    literal substring hits.  E.g. a query phrase ``"attack of opportunity"``
    can register a hit against section text ``"Attacks of Opportunity"``.
    The reported hit string is always the original (un-singularized) phrase
    from the query.
    """
    content = chunk.get("content", "")
    haystack = _singularize_text(f"{section_path_text} {content}".casefold())
    normalized_text = _singularize_text(query.normalized_text.casefold())
    lowered_section_path = _singularize_text(section_path_text.casefold())

    exact_phrase_hits: list[str] = []
    if _contains_phrase_on_token_boundaries(haystack, normalized_text):
        exact_phrase_hits.append(query.normalized_text)

    protected_phrase_hits = [
        phrase
        for phrase in query.protected_phrases
        if _contains_phrase_on_token_boundaries(
            haystack, _singularize_text(phrase.casefold())
        )
    ]

    query_terms = {
        _singularize(term)
        for token in query.tokens
        for term in re.findall(r"\w+", token.casefold())
    }
    haystack_terms = set(re.findall(r"\w+", haystack))
    token_overlap_count = len(query_terms & haystack_terms)

    section_phrases = [normalized_text] + [
        _singularize_text(phrase.casefold()) for phrase in query.protected_phrases
    ]

    return {
        "exact_phrase_hits": exact_phrase_hits,
        "protected_phrase_hits": protected_phrase_hits,
        "section_path_hit": any(
            _contains_phrase_on_token_boundaries(lowered_section_path, phrase)
            for phrase in section_phrases
            if phrase
        ),
        "token_overlap_count": token_overlap_count,
    }


def _contains_phrase_on_token_boundaries(haystack: str, phrase: str) -> bool:
    if not phrase:
        return False
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", haystack) is not None


def _singularize(word: str) -> str:
    """Collapse a single word to a naive singular form.

    The ``len(word) > N`` guards protect short tokens (``"is"``, ``"us"``) from
    being stripped to empty/single-char garbage even if they slip past the
    exception list.
    """
    if word in _PLURAL_EXCEPTIONS:
        return word
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("es"):
        return word[:-2]
    if len(word) > 2 and word.endswith("s"):
        return word[:-1]
    return word


def _singularize_text(text: str) -> str:
    """Apply :func:`_singularize` to each ``\\w+`` run, preserving the rest."""
    return re.sub(r"\w+", lambda m: _singularize(m.group(0)), text)
