"""Declarative content-type registry for entry detection.

A ContentTypeConfig binds:
  - a semantic identity (name, category, chunk_type)
  - a shape family (e.g., entry_with_statblock)
  - shape parameters (per-shape configuration)
  - an optional file_match allowlist (glob patterns)

The registry is loaded from a YAML config file and consumed by the
entry annotator. Downstream code never imports this module — annotations
on blocks carry the semantic payload forward.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Any

import yaml


@dataclass(frozen=True)
class ContentTypeConfig:
    name: str
    category: str
    chunk_type: str
    shape: str
    shape_params: dict[str, Any]
    file_match: list[str] | None = None


def load_content_types(yaml_text: str) -> list[ContentTypeConfig]:
    """Parse YAML content_types declarations into config objects."""
    data = yaml.safe_load(yaml_text)
    if not isinstance(data, dict) or "content_types" not in data:
        raise ValueError("content_types YAML must have top-level 'content_types' list")
    types: list[ContentTypeConfig] = []
    for entry in data["content_types"]:
        types.append(ContentTypeConfig(
            name=entry["name"],
            category=entry["category"],
            chunk_type=entry["chunk_type"],
            shape=entry["shape"],
            shape_params=entry.get("shape_params", {}),
            file_match=entry.get("file_match"),
        ))
    return types


def eligible_types_for_file(
    file_name: str,
    types: list[ContentTypeConfig],
) -> list[ContentTypeConfig]:
    """Return the subset of types eligible for a file.

    A type is eligible when:
      - file_match is None (always eligible), OR
      - file_name matches at least one glob in file_match.
    """
    eligible: list[ContentTypeConfig] = []
    for t in types:
        if t.file_match is None:
            eligible.append(t)
            continue
        if any(fnmatch.fnmatch(file_name, pattern) for pattern in t.file_match):
            eligible.append(t)
    return eligible
