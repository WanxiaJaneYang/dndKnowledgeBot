"""Phase 1 retrieval query normalization."""
from __future__ import annotations

import re

from .term_assets import get_default_term_assets


NATURAL_LANGUAGE_PREFIXES = (
    "what ",
    "how ",
    "when ",
    "where ",
    "why ",
    "who ",
    "which ",
)


def normalize_query(query: str) -> dict:
    """Normalize a user query into a thin retrieval-facing contract."""
    assets = get_default_term_assets()
    alias_map = assets["canonical_aliases"]
    protectable_phrases = sorted(
        set(assets["protected_phrases"]) | set(assets["surface_variants"]),
        key=lambda item: len(item.split()),
        reverse=True,
    )

    applied_rules: list[str] = []
    alias_expansions: list[dict[str, str]] = []

    normalized = query

    trimmed = normalized.strip()
    if trimmed != normalized:
        applied_rules.append("trim_whitespace")
        normalized = trimmed

    lowered = normalized.casefold()
    if lowered != normalized:
        applied_rules.append("case_fold")
        normalized = lowered

    cleaned = re.sub(r"[^\w\s]", " ", normalized)
    if cleaned != normalized:
        applied_rules.append("punctuation_cleanup")
        normalized = cleaned

    collapsed = re.sub(r"\s+", " ", normalized).strip()
    if collapsed != normalized:
        applied_rules.append("whitespace_normalization")
    normalized = collapsed

    alias_applied = False
    for source, target in alias_map.items():
        pattern = re.compile(rf"(?<!\w){re.escape(source)}(?!\w)")
        if pattern.search(normalized):
            normalized = pattern.sub(target, normalized)
            alias_expansions.append({"source": source, "target": target})
            alias_applied = True

    if alias_applied:
        applied_rules.append("alias_expansion")
        normalized = re.sub(r"\s+", " ", normalized).strip()

    protected_phrases = [
        phrase for phrase in protectable_phrases
        if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", normalized)
    ]
    tokens = _tokenize_with_protected_phrases(normalized, protected_phrases)

    return {
        "original_query": query,
        "normalized_text": normalized,
        "tokens": tokens,
        "protected_phrases": protected_phrases,
        "alias_expansions": alias_expansions,
        "applied_rules": applied_rules,
        "query_mode": _infer_query_mode(query, normalized),
    }


def _tokenize_with_protected_phrases(text: str, protected_phrases: list[str]) -> list[str]:
    words = text.split()
    if not words:
        return []

    protected_word_lists = [
        phrase.split() for phrase in sorted(protected_phrases, key=lambda item: len(item.split()), reverse=True)
    ]

    tokens: list[str] = []
    index = 0
    while index < len(words):
        matched_phrase = None
        for phrase_words in protected_word_lists:
            end_index = index + len(phrase_words)
            if words[index:end_index] == phrase_words:
                matched_phrase = " ".join(phrase_words)
                index = end_index
                break

        if matched_phrase is not None:
            tokens.append(matched_phrase)
            continue

        tokens.append(words[index])
        index += 1

    return tokens


def _infer_query_mode(original_query: str, normalized_text: str) -> str:
    original_trimmed = original_query.strip()
    lowered_original = original_trimmed.casefold()
    if original_trimmed.endswith("?") or lowered_original.startswith(NATURAL_LANGUAGE_PREFIXES):
        return "natural_language"
    if normalized_text.startswith(NATURAL_LANGUAGE_PREFIXES):
        return "natural_language"
    return "keyword_lookup"
