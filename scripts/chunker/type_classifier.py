"""Infer chunk_type from a canonical document's section_path."""
from __future__ import annotations

_LEGAL_TERMS = {"legal", "license", "ogl", "open game license", "open game content"}

# Chunk types defined in chunk.schema.json
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


def classify_chunk_type(section_path: list[str]) -> str:
    """Return a chunk_type value for the given section_path.

    Phase 1 heuristics (simple, expandable):
    - Legal / license text → generic
    - Section intro where the leaf title echoes the root → rule_section
    - Everything else → subsection
    """
    if not section_path:
        return "generic"

    joined_lower = " ".join(section_path).lower()

    # Legal or license documents
    if any(term in joined_lower for term in _LEGAL_TERMS):
        return "generic"

    root = _normalise(section_path[0])

    if len(section_path) == 1:
        # Single-element path — treat as top-level section.
        return "rule_section"

    leaf = _normalise(section_path[-1])
    # Leaf matches or closely echoes root — top-level section intro.
    if root == leaf or leaf.startswith(root) or root.startswith(leaf):
        return "rule_section"

    return "subsection"


def _normalise(s: str) -> str:
    return s.lower().replace(" ", "").replace("_", "").replace("-", "")
