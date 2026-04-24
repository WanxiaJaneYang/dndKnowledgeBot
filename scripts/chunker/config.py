"""Chunker configuration with sensible defaults."""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

import yaml


@dataclass(frozen=True)
class ChunkerConfig:
    child_threshold_chars: int = 6000
    paragraph_group_target_chars: int = 2000
    paragraph_group_max_chars: int = 3000


def load_chunker_config(yaml_text: str) -> ChunkerConfig:
    if not yaml_text or not yaml_text.strip():
        return ChunkerConfig()
    data: Any = yaml.safe_load(yaml_text)
    if not data:
        return ChunkerConfig()
    if not isinstance(data, dict):
        raise ValueError(
            f"chunker config YAML root must be a mapping, got {type(data).__name__}. "
            f"Expected fields: {sorted(f.name for f in fields(ChunkerConfig))}."
        )
    valid_fields = {f.name for f in fields(ChunkerConfig)}
    overrides: dict[str, Any] = {}
    for key, value in data.items():
        if key not in valid_fields:
            continue
        # All current fields are positive ints. Validate type + range so a
        # parseable but invalid value (quoted numeric, zero, negative)
        # surfaces as a clear error instead of an opaque downstream crash
        # (TypeError on arithmetic, infinite loop in _enforce_max_chars).
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(
                f"chunker config field '{key}' must be int, got {type(value).__name__}: {value!r}"
            )
        if value <= 0:
            raise ValueError(
                f"chunker config field '{key}' must be positive, got {value}"
            )
        overrides[key] = value
    return ChunkerConfig(**overrides)
