from __future__ import annotations

import json
import shutil
from pathlib import Path


def load_manifest(manifest_path: Path) -> dict:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def resolve_repo_relative_path(repo_root: Path, manifest_path: str) -> Path:
    resolved_repo_root = repo_root.resolve()
    resolved_path = (resolved_repo_root / manifest_path).resolve()
    if resolved_repo_root not in resolved_path.parents and resolved_path != resolved_repo_root:
        raise ValueError(f"Manifest path escapes repository root: {manifest_path}")
    return resolved_path


def remove_directory_if_present(path: Path, repo_root: Path) -> None:
    if not path.exists():
        return

    resolved_repo_root = repo_root.resolve()
    resolved_path = path.resolve()
    if resolved_path == resolved_repo_root:
        raise RuntimeError(f"Refusing to remove repository root: {resolved_path}")
    if resolved_repo_root not in resolved_path.parents:
        raise RuntimeError(f"Refusing to remove path outside repo root: {resolved_path}")

    shutil.rmtree(resolved_path)
