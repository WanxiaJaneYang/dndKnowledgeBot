"""Pre-retrieval hard filters for candidate chunks.

Loads retrieval_filters.yaml and applies edition, source-type,
authority-level, and source-exclusion constraints before any
scoring or ranking takes place.
"""
from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FILTER_CONFIG = REPO_ROOT / "configs" / "retrieval_filters.yaml"


@dataclass(frozen=True)
class RetrievalConstraints:
    """Explicit representation of hard filters for a retrieval pass."""

    editions: frozenset[str]
    source_types: frozenset[str]
    authority_levels: frozenset[str]
    excluded_source_ids: frozenset[str]

    def accepts(self, chunk_meta: dict[str, Any]) -> bool:
        """Return True if chunk metadata passes all hard filters."""
        edition = chunk_meta.get("edition", "")
        source_type = chunk_meta.get("source_type", "")
        authority_level = chunk_meta.get("authority_level", "")
        source_id = chunk_meta.get("source_id", "")

        if edition not in self.editions:
            return False
        if source_type not in self.source_types:
            return False
        if authority_level not in self.authority_levels:
            return False
        if source_id in self.excluded_source_ids:
            return False
        return True

    def rejection_reason(self, chunk_meta: dict[str, Any]) -> str | None:
        """Return a human-readable reason if rejected, else None."""
        edition = chunk_meta.get("edition", "")
        source_type = chunk_meta.get("source_type", "")
        authority_level = chunk_meta.get("authority_level", "")
        source_id = chunk_meta.get("source_id", "")

        if edition not in self.editions:
            return f"edition '{edition}' not in {sorted(self.editions)}"
        if source_type not in self.source_types:
            return f"source_type '{source_type}' not in {sorted(self.source_types)}"
        if authority_level not in self.authority_levels:
            return f"authority_level '{authority_level}' not in {sorted(self.authority_levels)}"
        if source_id in self.excluded_source_ids:
            return f"source_id '{source_id}' is explicitly excluded"
        return None


@dataclass
class FilterResult:
    """Outcome of applying hard filters to a set of candidates."""

    accepted: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    rejection_reasons: dict[int, str] = field(default_factory=dict)
    constraints: RetrievalConstraints | None = None

    @property
    def empty(self) -> bool:
        return len(self.accepted) == 0


def load_filter_config(path: Path | None = None) -> dict:
    """Load the retrieval filter YAML config."""
    config_path = path or DEFAULT_FILTER_CONFIG
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_constraints(config: dict | None = None) -> RetrievalConstraints:
    """Build a RetrievalConstraints from a config dict (or the default file)."""
    if config is None:
        config = load_filter_config()
    return RetrievalConstraints(
        editions=frozenset(config.get("editions", [])),
        source_types=frozenset(config.get("source_types", [])),
        authority_levels=frozenset(config.get("authority_levels", [])),
        excluded_source_ids=frozenset(config.get("excluded_source_ids", [])),
    )


def apply_filters(
    candidates: list[dict[str, Any]],
    constraints: RetrievalConstraints | None = None,
) -> FilterResult:
    """Apply hard filters to candidate chunks and return a FilterResult."""
    if constraints is None:
        constraints = build_constraints()

    result = FilterResult(constraints=constraints)
    for i, candidate in enumerate(candidates):
        meta = candidate.get("metadata", candidate)
        reason = constraints.rejection_reason(meta)
        if reason is None:
            result.accepted.append(candidate)
        else:
            result.rejected.append(candidate)
            result.rejection_reasons[i] = reason

    return result
