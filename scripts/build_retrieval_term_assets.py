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

MANUAL_RUNTIME_TERMS = {
    "ability check",
    "ability damage",
    "ability drain",
    "ability modifier",
    "ability modifiers",
    "armor bonus",
    "armor class",
    "armor check penalty",
    "arcane spell failure",
    "attack bonus",
    "attack roll",
    "attack rolls",
    "attack of opportunity",
    "attacks of opportunity",
    "base attack bonus",
    "base save bonus",
    "caster level",
    "challenge rating",
    "combat expertise",
    "concentration check",
    "concentration checks",
    "command undead",
    "coup de grace",
    "critical hit",
    "critical hits",
    "current hit points",
    "damage reduction",
    "death attack",
    "deflection bonus",
    "difficult terrain",
    "dispel check",
    "difficulty class",
    "divine spell",
    "energy damage",
    "energy drain",
    "experience points",
    "extraordinary abilities",
    "extraordinary ability",
    "flat footed",
    "flat footed armor class",
    "fortitude save",
    "free action",
    "full attack",
    "full attack action",
    "full round action",
    "full round actions",
    "granted power",
    "grapple check",
    "grapple checks",
    "hit dice",
    "hit die",
    "hit point",
    "hit points",
    "key ability",
    "level adjustment",
    "manifester level",
    "melee touch attack",
    "melee touch attacks",
    "move action",
    "natural armor bonus",
    "negative energy",
    "nonlethal damage",
    "nonplayer character",
    "player character",
    "point of origin",
    "range increment",
    "ranged touch attack",
    "ranged touch attacks",
    "reflex save",
    "resistance bonus",
    "resistance to energy",
    "saving throw",
    "saving throws",
    "shield bonus",
    "size modifier",
    "skill check",
    "skill checks",
    "spell completion",
    "spell completion item",
    "spell failure",
    "spell like abilities",
    "spell like ability",
    "spell resistance",
    "spell trigger",
    "spell trigger item",
    "standard action",
    "supernatural abilities",
    "supernatural ability",
    "temporary hit points",
    "touch attack",
    "touch attacks",
    "touch armor class",
    "touch spell",
    "touch spells",
    "turning check",
    "two handed weapon",
    "unarmed strike",
    "turn resistance",
    "turn undead",
    "turn or rebuke undead",
    "use activated",
    "will save",
}

SURFACE_VARIANTS = sorted({
    "attacks of opportunity",
    "base attack bonuses",
    "base save bonuses",
    "challenge ratings",
    "difficulty classes",
    "flat-footed",
    "flat-footed armor class",
    "flat-footed condition",
    "fort save",
    "free actions",
    "full attack actions",
    "move actions",
    "saving throw",
    "saving throws",
    "spell-like abilities",
    "spell-like ability",
    "standard actions",
    "touch attack",
    "touch attacks",
    "touch ac",
    "turn or rebuke undead",
    "turning checks",
    "turning undead",
    "two-handed weapon",
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
    reviewed = sorted(MANUAL_RUNTIME_TERMS)

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


if __name__ == "__main__":
    write_term_assets()
