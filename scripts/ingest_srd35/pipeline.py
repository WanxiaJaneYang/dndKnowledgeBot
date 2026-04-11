from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .constants import EXTRACTION_CAVEATS, INGESTION_NOTES
from .paths import remove_directory_if_present, resolve_repo_relative_path
from .rtf_decoder import decode_rtf_text


def _sha1_bytes(payload: bytes) -> str:
    digest = hashlib.sha1()
    digest.update(payload)
    return digest.hexdigest()


def _sha1_text(text: str) -> str:
    return _sha1_bytes(text.encode("utf-8"))


def _sanitize_identifier(value: str) -> str:
    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return normalized or "unknown"


def build_source_ref(manifest: dict) -> dict:
    return {
        "source_id": manifest["source_id"],
        "title": manifest["title"],
        "edition": manifest["edition"],
        "source_type": manifest["source_type"],
        "authority_level": manifest["authority_level"],
    }


def _write_reports(
    *,
    manifest: dict,
    repo_root: Path,
    raw_root: Path,
    expanded_root: Path,
    extracted_root: Path,
    canonical_root: Path,
    ingested_at: str,
    extraction_records: list[dict],
    canonical_records: list[dict],
) -> tuple[Path, Path]:
    extracted_report = {
        "source_id": manifest["source_id"],
        "generated_at_utc": ingested_at,
        "input_root": str(raw_root.relative_to(repo_root)),
        "expanded_root": str(expanded_root.relative_to(repo_root)),
        "ingestion_notes": INGESTION_NOTES,
        "extraction_caveats": EXTRACTION_CAVEATS,
        "records": extraction_records,
    }
    extracted_report_path = extracted_root / "extraction_report.json"
    extracted_report_path.write_text(json.dumps(extracted_report, indent=2) + "\n", encoding="utf-8")

    canonical_report = {
        "source_id": manifest["source_id"],
        "generated_at_utc": ingested_at,
        "canonical_count": len(canonical_records),
        "ingestion_notes": INGESTION_NOTES,
        "extraction_caveats": EXTRACTION_CAVEATS,
        "records": canonical_records,
    }
    canonical_report_path = canonical_root / "canonical_report.json"
    canonical_report_path.write_text(json.dumps(canonical_report, indent=2) + "\n", encoding="utf-8")
    return extracted_report_path, canonical_report_path


def ingest_source(
    manifest: dict,
    repo_root: Path,
    *,
    force: bool = False,
    limit: int | None = None,
) -> dict:
    layout = manifest["local_layout"]
    raw_root = resolve_repo_relative_path(repo_root, layout["raw_root"])
    expanded_root = resolve_repo_relative_path(repo_root, layout["expanded_root"])
    extracted_root = resolve_repo_relative_path(repo_root, layout["extracted_root"])
    canonical_root = resolve_repo_relative_path(repo_root, layout["canonical_root"])

    if force:
        remove_directory_if_present(extracted_root, repo_root)
        remove_directory_if_present(canonical_root, repo_root)

    extracted_text_root = extracted_root / "text"
    extracted_text_root.mkdir(parents=True, exist_ok=True)
    canonical_root.mkdir(parents=True, exist_ok=True)

    rtf_files = sorted(expanded_root.glob("*.rtf"))
    if limit is not None:
        rtf_files = rtf_files[:limit]

    source_ref = build_source_ref(manifest)
    ingested_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    extraction_records: list[dict] = []
    canonical_records: list[dict] = []

    for rtf_path in rtf_files:
        raw_bytes = rtf_path.read_bytes()
        decoded = decode_rtf_text(raw_bytes.decode("latin-1", errors="ignore"))
        raw_checksum = _sha1_bytes(raw_bytes)
        extracted_checksum = _sha1_text(decoded)

        source_location = f"rtf/{rtf_path.name}"
        section_name = rtf_path.stem
        section_path = [section_name]
        doc_slug = _sanitize_identifier(section_name)
        document_id = f"{manifest['source_id']}::{doc_slug}"

        extracted_path = extracted_text_root / f"{doc_slug}.txt"
        extracted_path.write_text(decoded + "\n", encoding="utf-8")

        canonical_doc = {
            "document_id": document_id,
            "source_ref": source_ref,
            "locator": {"section_path": section_path, "source_location": source_location},
            "content": decoded,
            "document_title": section_name,
            "source_checksum": raw_checksum,
            "ingested_at": ingested_at,
        }
        canonical_path = canonical_root / f"{doc_slug}.json"
        canonical_path.write_text(json.dumps(canonical_doc, indent=2) + "\n", encoding="utf-8")

        extraction_records.append(
            {
                "file_name": rtf_path.name,
                "source_location": source_location,
                "section_path": section_path,
                "raw_sha1": raw_checksum,
                "extracted_sha1": extracted_checksum,
                "extracted_text_path": str(extracted_path.relative_to(repo_root)),
                "ingestion_notes": INGESTION_NOTES,
                "extraction_caveats": EXTRACTION_CAVEATS,
            }
        )
        canonical_records.append(
            {
                "document_id": document_id,
                "canonical_path": str(canonical_path.relative_to(repo_root)),
                "source_checksum": raw_checksum,
                "section_path": section_path,
                "source_location": source_location,
            }
        )

    extracted_report_path, canonical_report_path = _write_reports(
        manifest=manifest,
        repo_root=repo_root,
        raw_root=raw_root,
        expanded_root=expanded_root,
        extracted_root=extracted_root,
        canonical_root=canonical_root,
        ingested_at=ingested_at,
        extraction_records=extraction_records,
        canonical_records=canonical_records,
    )

    return {
        "source_id": manifest["source_id"],
        "extracted_root": str(extracted_root),
        "canonical_root": str(canonical_root),
        "documents_written": len(canonical_records),
        "extraction_report": str(extracted_report_path),
        "canonical_report": str(canonical_report_path),
    }
