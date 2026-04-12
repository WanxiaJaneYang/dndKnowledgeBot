"""Build reviewed retrieval term assets from extracted SRD candidates."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.extract_retrieval_terms import DEFAULT_CANONICAL_ROOT, DEFAULT_CHUNK_ROOT, extract_term_candidates

TERM_ROOT = REPO_ROOT / "configs" / "retrieval_terms"

EXCLUDE_EXACT = {
    "abilities and manifesters",
    "abilities and spellcasters",
    "ability name",
    "class features",
    "class skills",
    "combat statistics",
    "descriptive text",
    "skill descriptions",
    "spell descriptions",
    "statistics block",
    "types of feats",
    "types of epic feats",
}

EXCLUDE_SUFFIXES = (
    " general",
    " epic",
    " as characters",
    " descriptions",
    " domain spells",
)

EXCLUDE_PREFIXES = (
    "acquiring ",
    "adding ",
    "buying ",
    "choosing ",
    "combining ",
    "craft ",
    "create ",
    "creating ",
    "designing ",
    "developing ",
    "determining ",
    "improved ",
    "improving ",
    "reading ",
    "repairing ",
    "selling ",
    "training ",
    "using ",
)

EXCLUDE_CONTAINS = (
    "/",
    " 0 ",
    " 1 ",
    " 2 ",
    " 3 ",
    " 4 ",
    " 5 ",
    " 6 ",
    " 7 ",
    " 8 ",
    " 9 ",
)

MANUAL_RUNTIME_TERMS = {
    "armor class",
    "attack bonus",
    "attack of opportunity",
    "attacks of opportunity",
    "base attack bonus",
    "base save bonus",
    "caster level",
    "challenge rating",
    "combat expertise",
    "damage reduction",
    "difficulty class",
    "extraordinary abilities",
    "extraordinary ability",
    "full attack",
    "full attack action",
    "grapple checks",
    "hit dice",
    "hit die",
    "hit point",
    "hit points",
    "initiative",
    "level adjustment",
    "manifester level",
    "nonlethal damage",
    "saving throw",
    "saving throws",
    "spell failure",
    "spell like abilities",
    "spell like ability",
    "spell resistance",
    "supernatural abilities",
    "supernatural ability",
    "temporary hit points",
    "touch attack",
    "touch attacks",
    "turn resistance",
    "turn undead",
    "turn or rebuke undead",
}

SURFACE_VARIANTS = sorted({
    "attacks of opportunity",
    "base attack bonuses",
    "base save bonuses",
    "challenge ratings",
    "difficulty classes",
    "flat-footed",
    "flat-footed condition",
    "full attack actions",
    "saving throw",
    "saving throws",
    "spell-like abilities",
    "spell-like ability",
    "touch attack",
    "touch attacks",
    "turn or rebuke undead",
    "turning undead",
})

CANONICAL_ALIASES = {
    "ac": "armor class",
    "aoo": "attack of opportunity",
    "bab": "base attack bonus",
    "cl": "caster level",
    "con": "constitution",
    "cr": "challenge rating",
    "dc": "difficulty class",
    "dex": "dexterity",
    "dr": "damage reduction",
    "ex": "extraordinary abilities",
    "hd": "hit dice",
    "hp": "hit points",
    "int": "intelligence",
    "ref": "reflex",
    "sr": "spell resistance",
    "sp": "spell like abilities",
    "str": "strength",
    "su": "supernatural abilities",
    "wis": "wisdom",
    "xp": "experience points",
}


def build_term_assets() -> dict:
    extracted = extract_term_candidates(DEFAULT_CANONICAL_ROOT, DEFAULT_CHUNK_ROOT)
    reviewed = sorted(
        set(MANUAL_RUNTIME_TERMS)
        | {
            term for term in extracted["section_title_candidates"]
            if _is_runtime_protectable(term)
        }
    )

    candidates = sorted(set(extracted["protected_phrase_candidates"]) | set(extracted["content_phrase_candidates"]))

    return {
        "protected_phrases": reviewed,
        "canonical_aliases": CANONICAL_ALIASES,
        "surface_variants": SURFACE_VARIANTS,
        "extraction_candidates": candidates,
    }


def write_term_assets() -> dict:
    assets = build_term_assets()
    TERM_ROOT.mkdir(parents=True, exist_ok=True)
    for filename, payload in {
        "protected_phrases.json": assets["protected_phrases"],
        "canonical_aliases.json": assets["canonical_aliases"],
        "surface_variants.json": assets["surface_variants"],
        "extraction_candidates.json": assets["extraction_candidates"],
    }.items():
        (TERM_ROOT / filename).write_text(
            json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    return assets


def _is_runtime_protectable(term: str) -> bool:
    if term in EXCLUDE_EXACT:
        return False
    if any(term.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return False
    if any(term.endswith(suffix) for suffix in EXCLUDE_SUFFIXES):
        return False
    if any(fragment in term for fragment in EXCLUDE_CONTAINS):
        return False
    if term.startswith("cr "):
        return False
    if term.endswith(" spells") or term.endswith(" powers") or term.endswith(" items"):
        return False
    if term.endswith(" domain"):
        return False
    return True


if __name__ == "__main__":
    write_term_assets()
