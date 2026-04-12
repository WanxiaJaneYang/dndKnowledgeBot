"""Infer chunk_type from a canonical document's section_path."""
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


def classify_chunk_type(section_path: list[str]) -> str:
    """Return a chunk_type value for the given section_path.

    Phase 1 heuristics (simple, expandable):
    - Legal / license text → generic
    - Section intro where the leaf title echoes the root → rule_section
    - Everything else → subsection
    """
    if not section_path:
        chunk_type = "generic"
    elif _is_legal(section_path):
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


def _normalize(s: str) -> str:
    return s.lower().replace(" ", "").replace("_", "").replace("-", "")
