"""Baseline chunker pipeline: canonical document → chunk objects.

Phase 1 strategy: one canonical document produces one chunk.
The ingestion pipeline already splits by section and entry; this layer
assigns chunk metadata, types adjacency links, and validates the output.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .schema_validation import validate_chunks
from .type_classifier import classify_chunk_type

CHUNK_VERSION = "v1-section-passthrough"


def _chunk_id(document_id: str) -> str:
    return f"chunk::{document_id}"


def _source_file_key(doc: dict) -> str:
    """Group key for within-file adjacency.

    Adjacency links are only meaningful within the same source file —
    a link crossing file boundaries would imply context continuity that
    doesn't exist. Derive the key from source_location (the part before '#')
    and fall back to section_path[0] when source_location is absent.
    """
    locator = doc.get("locator", {})
    source_location = locator.get("source_location", "")
    if source_location:
        return source_location.split("#")[0]
    section_path = locator.get("section_path", [])
    if section_path:
        return section_path[0]
    return "__unknown__"


def _build_chunk(
    canonical_doc: dict,
    *,
    previous_chunk_id: str | None,
    next_chunk_id: str | None,
) -> dict:
    document_id = canonical_doc["document_id"]
    section_path = canonical_doc.get("locator", {}).get("section_path", [])
    content = canonical_doc.get("content", "")

    chunk: dict = {
        "chunk_id": _chunk_id(document_id),
        "document_id": document_id,
        "source_ref": canonical_doc["source_ref"],
        "locator": canonical_doc["locator"],
        "chunk_type": classify_chunk_type(section_path, content),
        "content": content,
        "chunk_version": CHUNK_VERSION,
    }
    if previous_chunk_id is not None:
        chunk["previous_chunk_id"] = previous_chunk_id
    if next_chunk_id is not None:
        chunk["next_chunk_id"] = next_chunk_id
    return chunk


def chunk_source(
    canonical_root: Path,
    output_root: Path,
    repo_root: Path,
    source_id: str | None = None,
    *,
    force: bool = False,
    require_schema_validation: bool = False,
) -> dict:
    """Read all canonical docs from canonical_root, produce chunks in output_root.

    source_id is written to the chunk report. When None it is derived from
    the canonical docs; when provided it must match every doc's source_ref.source_id.

    Callers that accept user-supplied paths (e.g. the CLI) are responsible for
    validating that output_root is inside repo_root before calling with force=True.
    """
    if not canonical_root.exists():
        raise FileNotFoundError(f"Canonical root not found: {canonical_root}")

    if output_root.exists() and not force:
        raise FileExistsError(
            f"Chunk output directory already exists: {output_root}. "
            "Re-run with --force to regenerate."
        )
    if force and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    # Load and sort canonical docs so adjacency links are deterministic.
    canonical_paths = sorted(canonical_root.glob("*.json"))
    canonical_paths = [p for p in canonical_paths if p.name != "canonical_report.json"]

    canonical_docs = []
    for path in canonical_paths:
        doc = json.loads(path.read_text(encoding="utf-8"))
        canonical_docs.append((path.stem, doc))

    # Derive or validate source_id from canonical docs so the report is
    # always consistent with the chunk source_ref fields.
    if canonical_docs:
        canonical_source_ids = {doc["source_ref"]["source_id"] for _, doc in canonical_docs}
        if len(canonical_source_ids) > 1:
            raise ValueError(
                f"Canonical docs contain multiple source_ids: {canonical_source_ids}. "
                "chunk_source expects a single-source canonical root."
            )
        derived_source_id = canonical_source_ids.pop()
        if source_id is not None and source_id != derived_source_id:
            raise ValueError(
                f"Provided source_id {source_id!r} does not match canonical docs "
                f"source_ref.source_id {derived_source_id!r}."
            )
        source_id = derived_source_id
    elif source_id is None:
        source_id = "unknown"

    # Group by source file so adjacency links stay within the same file.
    # A cross-file link would imply context continuity that doesn't exist.
    by_file: dict[str, list[tuple[str, dict]]] = {}
    for stem, doc in canonical_docs:
        key = _source_file_key(doc)
        by_file.setdefault(key, []).append((stem, doc))

    # Build chunk objects with within-file adjacency only.
    chunks: list[tuple[str, dict]] = []
    for file_key, file_docs in by_file.items():
        n = len(file_docs)
        for i, (stem, doc) in enumerate(file_docs):
            prev_id = _chunk_id(file_docs[i - 1][1]["document_id"]) if i > 0 else None
            next_id = _chunk_id(file_docs[i + 1][1]["document_id"]) if i < n - 1 else None
            chunk = _build_chunk(doc, previous_chunk_id=prev_id, next_chunk_id=next_id)
            chunks.append((stem, chunk))

    # Validate before writing.
    chunked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    chunk_objects = [c for _, c in chunks]
    validation_result = validate_chunks(
        chunk_objects,
        repo_root,
        require_validation=require_schema_validation,
    )

    # Write chunk files.
    chunk_records: list[dict] = []
    for stem, chunk in chunks:
        chunk_path = output_root / f"{stem}.json"
        chunk_path.write_text(json.dumps(chunk, indent=2) + "\n", encoding="utf-8")
        try:
            display_path = str(chunk_path.relative_to(repo_root))
        except ValueError:
            display_path = str(chunk_path)
        chunk_records.append(
            {
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "chunk_type": chunk["chunk_type"],
                "chunk_path": display_path,
            }
        )

    # Write chunk report.
    report = {
        "source_id": source_id,
        "chunked_at_utc": chunked_at,
        "strategy": CHUNK_VERSION,
        "chunk_count": len(chunk_records),
        "schema_validation": validation_result,
        "records": chunk_records,
    }
    report_path = output_root / "chunk_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    return {
        "source_id": source_id,
        "canonical_root": str(canonical_root),
        "output_root": str(output_root),
        "chunks_written": len(chunk_records),
        "chunk_report": str(report_path),
        "schema_validation": validation_result,
    }
