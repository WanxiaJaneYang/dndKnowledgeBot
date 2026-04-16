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
    if normalized_text and normalized_text in haystack:
        exact_phrase_hits.append(query.normalized_text)

    protected_phrase_hits = [
        phrase for phrase in query.protected_phrases if phrase.casefold() in haystack
    ]

    query_terms = {
        token.casefold()
        for token in query.tokens
        if token and " " not in token
    }
    content_terms = set(re.findall(r"\w+", content.casefold()))
    token_overlap_count = len(query_terms & content_terms)

    return {
        "exact_phrase_hits": exact_phrase_hits,
        "protected_phrase_hits": protected_phrase_hits,
        "section_path_hit": any(
            phrase.casefold() in lowered_section_path
            for phrase in [query.normalized_text, *query.protected_phrases]
            if phrase
        ),
        "token_overlap_count": token_overlap_count,
    }
