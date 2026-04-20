"""End-to-end lexical retriever for Phase 1."""
from __future__ import annotations

from .contracts import NormalizedQuery


def _build_fts_expression(query: NormalizedQuery) -> str:
    """Build an FTS5 MATCH expression from a normalized query."""
    if not query.tokens:
        return ""

    protected_set = set(query.protected_phrases)
    parts: list[str] = []

    for token in query.tokens:
        if token in protected_set:
            parts.append(f'"{token}"')
        else:
            parts.append(token)

    # Prepend the full normalized text as a quoted phrase when it differs
    # from any single token — gives BM25 full-phrase match priority.
    if len(query.tokens) > 1:
        full_phrase = f'"{query.normalized_text}"'
        parts.insert(0, full_phrase)

    return " OR ".join(parts)
