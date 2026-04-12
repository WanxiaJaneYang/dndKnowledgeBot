"""Infer chunk_type from a canonical document's section_path and content."""
from __future__ import annotations

import re

# Token-level legal/license terms — matched against individual path tokens,
# not raw substrings, so "illegal" or "paralegal" do not trigger this.
_LEGAL_TOKENS = {"legal", "license", "ogl"}
_LEGAL_PHRASES = {"open game license", "open game content"}

# Chunk types defined in chunk.schema.json. Used as a post-classification
# guard to catch any drift between this module and the schema.
_VALID_TYPES = {
    "rule_section",
    "subsection",
    "spell_entry",
    "feat_entry",
    "skill_entry",
    "class_feature",
    "condition_entry",
    "glossary_entry",
    "table",
    "example",
    "sidebar",
    "errata_note",
    "faq_note",
    "paragraph_group",
    "generic",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def classify_chunk_type(section_path: list[str], content: str = "") -> str:
    """Return a chunk_type value for the given section_path and content.

    Phase 1 heuristics (simple, expandable):
    - Legal / license text → generic  (detected via section_path OR content)
    - Section intro where the leaf title echoes the root → rule_section
    - Everything else → subsection

    Content is checked as a fallback for sections whose path looks substantive
    but whose text is entirely OGL/license boilerplate (e.g. an intro section
    whose first sentence is the standard OGL notice).
    """
    if not section_path:
        chunk_type = "generic"
    elif _is_legal(section_path):
        chunk_type = "generic"
    elif content and _is_legal_content(content):
        chunk_type = "generic"
    elif len(section_path) == 1:
        chunk_type = "rule_section"
    else:
        root = _normalize(section_path[0])
        leaf = _normalize(section_path[-1])
        if root == leaf or leaf.startswith(root) or root.startswith(leaf):
            chunk_type = "rule_section"
        else:
            chunk_type = "subsection"

    assert chunk_type in _VALID_TYPES, (
        f"classify_chunk_type returned {chunk_type!r} which is not in chunk.schema.json enum. "
        "Update _VALID_TYPES or the classifier."
    )
    return chunk_type


def _is_legal(section_path: list[str]) -> bool:
    """Return True when section_path indicates a legal or license section.

    Matches whole tokens only (not substrings) to avoid false positives
    on words like 'illegal' or 'paralegal'.
    """
    joined_lower = " ".join(section_path).lower()
    # Check multi-word phrases first.
    if any(phrase in joined_lower for phrase in _LEGAL_PHRASES):
        return True
    # Then check individual tokens.
    tokens = set(_TOKEN_RE.findall(joined_lower))
    return bool(tokens & _LEGAL_TOKENS)


def _is_legal_content(content: str) -> bool:
    """Return True only when content is substantially OGL/license boilerplate.

    The first sentence is checked for OGL phrases. If found, the remainder of
    the content is inspected: if substantial rule content follows the OGL line
    the section is NOT demoted. Only sections whose content is essentially
    nothing but the OGL notice are classified as generic.
    """
    # Find end of first sentence.
    end = min(
        (content.find(c) for c in (".", "\n") if c in content),
        default=len(content),
    )
    first_sentence = content[: end + 1].lower()
    if not any(phrase in first_sentence for phrase in _LEGAL_PHRASES):
        return False
    # First sentence is OGL boilerplate — only demote if nothing substantial follows.
    remainder = content[end + 1:].strip()
    return len(remainder) < 50


def _normalize(s: str) -> str:
    return s.lower().replace(" ", "").replace("_", "").replace("-", "")
