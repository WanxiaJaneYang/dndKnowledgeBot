"""Pre-retrieval hard filters for candidate chunks.

Loads retrieval_filters.yaml and applies edition, source-type,
authority-level, and source-exclusion constraints before any
scoring or ranking takes place.
"""
from __future__ import annotations

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

    def accepts(self, chunk: dict[str, Any]) -> bool:
        """Return True if chunk passes all hard filters.

        Reads filter fields from ``source_ref`` (the real chunk shape)
        and falls back to top-level keys for flat metadata dicts.
        """
        ref = _extract_source_ref(chunk)
        edition = ref.get("edition", "")
        source_type = ref.get("source_type", "")
        authority_level = ref.get("authority_level", "")
        source_id = ref.get("source_id", "")

        if edition not in self.editions:
            return False
        if source_type not in self.source_types:
            return False
        if authority_level not in self.authority_levels:
            return False
        if source_id in self.excluded_source_ids:
            return False
        return True

    def rejection_reason(self, chunk: dict[str, Any]) -> str | None:
        """Return a human-readable reason if rejected, else None."""
        ref = _extract_source_ref(chunk)
        edition = ref.get("edition", "")
        source_type = ref.get("source_type", "")
        authority_level = ref.get("authority_level", "")
        source_id = ref.get("source_id", "")

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


def _extract_source_ref(chunk: dict[str, Any]) -> dict[str, Any]:
    """Return the source_ref sub-dict, falling back to the chunk itself."""
    return chunk.get("source_ref", chunk)


def load_filter_config(path: Path | None = None) -> dict:
    """Load the retrieval filter YAML config.

    PyYAML is imported lazily so that callers who never use hard
    filters (e.g. query normalization) don't pay the dependency cost.
    """
    import yaml

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
        reason = constraints.rejection_reason(candidate)
        if reason is None:
            result.accepted.append(candidate)
        else:
            result.rejected.append(candidate)
            result.rejection_reasons[i] = reason

    return result
