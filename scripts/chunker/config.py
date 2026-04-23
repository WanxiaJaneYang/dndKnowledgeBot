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
    data: dict[str, Any] | None = yaml.safe_load(yaml_text)
    if not data:
        return ChunkerConfig()
    valid_fields = {f.name for f in fields(ChunkerConfig)}
    overrides = {k: v for k, v in data.items() if k in valid_fields}
    return ChunkerConfig(**overrides)
