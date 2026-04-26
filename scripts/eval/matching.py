"""Tokenization and section/entry matching helpers for the eval tagger."""
from __future__ import annotations

import re

# Built-in stopword list — small, project-internal, no NLTK dependency.
_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "doing", "have", "has", "had", "having",
    "of", "in", "on", "at", "to", "for", "with", "by", "from",
    "and", "or", "but", "not", "no", "if", "then", "else",
    "i", "you", "he", "she", "it", "we", "they", "this", "that",
    "what", "when", "where", "who", "why", "how", "which",
    "can", "could", "would", "should", "may", "might", "must",
    "shall", "will",
})

_WORD = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> set[str]:
    """Lowercase, alphanumeric word tokens with stopwords removed."""
    return {t for t in _WORD.findall(text.lower()) if t not in _STOPWORDS}


def _looks_like_filename(s: str) -> bool:
    """Heuristic: treat as a filename if it ends in `.rtf` (pre-strip) or
    contains no whitespace and no colon (e.g. `combati`, `abilitiesandconditions`)."""
    return s.endswith(".rtf") or ("." in s) or (
        " " not in s and ":" not in s and len(s) > 0
    )


def extract_expected_head(expected: tuple[str, ...]) -> str | None:
    """First element after `.rtf` strip + lowercase, with fallback to [1].

    See spec §3.3 for the exact rule. Returns None only when called on ``()``;
    callers are expected to short-circuit before reaching here.
    """
    if not expected:
        return None
    head = expected[0].lower()
    if head.endswith(".rtf"):
        head = head[: -len(".rtf")]
    # If still filename-shaped and a second element exists, prefer it.
    if _looks_like_filename(head) and len(expected) >= 2:
        return expected[1].lower()
    return head


def extract_expected_tail(expected: tuple[str, ...]) -> str | None:
    """Last element of the expected list, lowercased."""
    if not expected:
        return None
    return expected[-1].lower()


def section_root_matches(
    citation_section_path: tuple[str, ...], expected_head: str
) -> bool:
    """True if any section_path element substring-matches expected_head, or
    the colon-prefix matches."""
    expected_prefix = expected_head.split(":", 1)[0].strip()
    for elem in citation_section_path:
        elem_lower = elem.lower()
        if expected_head in elem_lower:
            return True
        elem_prefix = elem_lower.split(":", 1)[0].strip()
        if expected_prefix and elem_prefix == expected_prefix:
            return True
    return False


def entry_matches(
    citation_section_path: tuple[str, ...],
    citation_entry_title: str | None,
    expected_tail: str,
) -> bool:
    """True if expected_tail is a substring of any section_path element or
    of the citation's entry_title."""
    for elem in citation_section_path:
        if expected_tail in elem.lower():
            return True
    if citation_entry_title and expected_tail in citation_entry_title.lower():
        return True
    return False
