"""File-backed retrieval term assets."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TERM_ASSET_ROOT = REPO_ROOT / "configs" / "retrieval_terms"


def load_term_assets(asset_root: Path | None = None) -> dict:
    """Load retrieval term assets from JSON files."""
    root = asset_root or TERM_ASSET_ROOT
    return {
        "protected_phrases": _load_json(root / "protected_phrases.json"),
        "canonical_aliases": _load_json(root / "canonical_aliases.json"),
        "surface_variants": _load_json(root / "surface_variants.json"),
        "extraction_candidates": _load_json(root / "extraction_candidates.json"),
    }


@lru_cache(maxsize=1)
def get_default_term_assets() -> dict:
    return load_term_assets()


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
