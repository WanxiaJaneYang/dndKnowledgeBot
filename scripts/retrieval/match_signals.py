"""Match-signal helpers for lexical retrieval candidates."""
from __future__ import annotations

import re
from typing import Any

from .contracts import NormalizedQuery


def build_match_signals(
    query: NormalizedQuery,
    chunk: dict[str, Any],
    section_path_text: str,
) -> dict[str, Any]:
    """Compute lightweight lexical match signals for a candidate chunk."""
    content = chunk.get("content", "")
    haystack = f"{section_path_text} {content}".casefold()
    normalized_text = query.normalized_text.casefold()
    lowered_section_path = section_path_text.casefold()

    exact_phrase_hits: list[str] = []
    if _contains_phrase_on_token_boundaries(haystack, normalized_text):
        exact_phrase_hits.append(query.normalized_text)

    protected_phrase_hits = [
        phrase
        for phrase in query.protected_phrases
        if _contains_phrase_on_token_boundaries(haystack, phrase.casefold())
    ]

    query_terms = {
        term
        for token in query.tokens
        for term in re.findall(r"\w+", token.casefold())
    }
    haystack_terms = set(re.findall(r"\w+", haystack))
    token_overlap_count = len(query_terms & haystack_terms)

    return {
        "exact_phrase_hits": exact_phrase_hits,
        "protected_phrase_hits": protected_phrase_hits,
        "section_path_hit": any(
            _contains_phrase_on_token_boundaries(lowered_section_path, phrase.casefold())
            for phrase in [query.normalized_text, *query.protected_phrases]
            if phrase
        ),
        "token_overlap_count": token_overlap_count,
    }


def _contains_phrase_on_token_boundaries(haystack: str, phrase: str) -> bool:
    if not phrase:
        return False
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", haystack) is not None
