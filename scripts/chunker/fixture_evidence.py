"""Fixture-based evidence helpers for the chunker.

Chunks the committed fixture canonical docs and provides read/write
helpers for golden outputs — mirrors scripts/ingest_srd35/fixture_evidence.py.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .pipeline import chunk_source


def run_fixture_chunking(repo_root: Path) -> dict:
    """Chunk the committed fixture canonical docs and return chunk objects keyed by filename."""
    canonical_root = repo_root / "tests" / "fixtures" / "expected" / "canonical"
    if not canonical_root.exists():
        raise FileNotFoundError(f"Fixture canonical root not found: {canonical_root}")

    with tempfile.TemporaryDirectory() as tmp:
        output_root = Path(tmp) / "chunks"
        chunk_source(
            canonical_root=canonical_root,
            output_root=output_root,
            repo_root=repo_root,
            source_id="srd_35_fixture",
            force=True,
            require_schema_validation=False,
        )
        chunks = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(output_root.glob("*.json"))
            if path.name != "chunk_report.json"
        }
    return {"chunks": chunks}


def write_golden_chunk_outputs(repo_root: Path, evidence: dict) -> None:
    """Write chunk golden outputs to tests/fixtures/expected/chunks/."""
    chunks_root = repo_root / "tests" / "fixtures" / "expected" / "chunks"
    chunks_root.mkdir(parents=True, exist_ok=True)

    for path in chunks_root.glob("*.json"):
        if path.is_file():
            path.unlink()

    for name, payload in evidence["chunks"].items():
        (chunks_root / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_golden_chunk_outputs(repo_root: Path) -> dict:
    """Load chunk golden outputs from tests/fixtures/expected/chunks/."""
    chunks_root = repo_root / "tests" / "fixtures" / "expected" / "chunks"
    chunks = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(chunks_root.glob("*.json"))
    }
    return {"chunks": chunks}
