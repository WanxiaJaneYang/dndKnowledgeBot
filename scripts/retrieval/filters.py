"""Pre-retrieval hard filters for candidate chunks.

Derives default constraints from source_registry.yaml (the single
source of truth for admitted sources) and applies edition, source-type,
authority-level, and source-exclusion filters before any scoring.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_REGISTRY = REPO_ROOT / "configs" / "source_registry.yaml"


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


def _load_source_registry(path: Path | None = None) -> list[dict]:
    """Load and validate source entries from source_registry.yaml."""
    import yaml

    registry_path = path or SOURCE_REGISTRY
    with registry_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"Source registry at {registry_path} must be a YAML mapping "
            f"with a 'sources' key, got {type(data).__name__}"
        )
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError(
            f"Source registry at {registry_path} has 'sources' of type "
            f"{type(sources).__name__}, expected a list"
        )
    return sources


def build_constraints(
    *,
    registry_path: Path | None = None,
    excluded_source_ids: frozenset[str] | None = None,
) -> RetrievalConstraints:
    """Derive constraints from the admitted sources in source_registry.yaml.

    Only sources whose status is not ``planned_later`` contribute to
    the allowlists.  This keeps the filter boundary in sync with what
    the project has actually admitted — no second config to drift.
    """
    sources = _load_source_registry(registry_path)

    editions: set[str] = set()
    source_types: set[str] = set()
    authority_levels: set[str] = set()

    for src in sources:
        if src.get("status") == "planned_later":
            continue
        if edition := src.get("edition"):
            editions.add(edition)
        if stype := src.get("source_type"):
            source_types.add(stype)
        if auth := src.get("authority_level"):
            authority_levels.add(auth)

    return RetrievalConstraints(
        editions=frozenset(editions),
        source_types=frozenset(source_types),
        authority_levels=frozenset(authority_levels),
        excluded_source_ids=excluded_source_ids or frozenset(),
    )


@lru_cache(maxsize=1)
def _default_constraints() -> RetrievalConstraints:
    """Cached default constraints derived from source_registry.yaml.

    Avoids re-parsing the registry on every per-query ``apply_filters``
    call.  The registry is small and static at runtime, so a single
    cached instance is safe.  Tests that mutate the registry can call
    ``_default_constraints.cache_clear()``.
    """
    return build_constraints()


def apply_filters(
    candidates: list[dict[str, Any]],
    constraints: RetrievalConstraints | None = None,
) -> FilterResult:
    """Apply hard filters to candidate chunks and return a FilterResult."""
    if constraints is None:
        constraints = _default_constraints()

    result = FilterResult(constraints=constraints)
    for i, candidate in enumerate(candidates):
        reason = constraints.rejection_reason(candidate)
        if reason is None:
            result.accepted.append(candidate)
        else:
            result.rejected.append(candidate)
            result.rejection_reasons[i] = reason

    return result
