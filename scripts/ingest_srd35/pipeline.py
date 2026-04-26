from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .boundary_filter import apply_boundary_filters
from .constants import EXTRACTION_CAVEATS, INGESTION_NOTES
from .content_types import eligible_types_for_file, load_content_types
from .entry_annotator import annotate_entries
from .extraction_ir import build_extraction_ir
from .paths import remove_directory_if_present, resolve_repo_relative_path
from .rtf_decoder import decode_rtf_spans, decode_rtf_text
from .schema_validation import validate_canonical_docs
from .sectioning import sanitize_identifier, split_sections_from_blocks


def _sha1_bytes(payload: bytes) -> str:
    digest = hashlib.sha1()
    digest.update(payload)
    return digest.hexdigest()


def _sha1_text(text: str) -> str:
    return _sha1_bytes(text.encode("utf-8"))


def build_source_ref(manifest: dict) -> dict:
    return {
        "source_id": manifest["source_id"],
        "title": manifest["title"],
        "edition": manifest["edition"],
        "source_type": manifest["source_type"],
        "authority_level": manifest["authority_level"],
    }


def _compute_processing_hints(section: dict, meta: dict) -> dict:
    """Build processing_hints dict from section + entry_metadata.

    Reads stat_block_end_char directly from entry_metadata when the
    sectioner stamped it (entry_with_statblock shape). No content
    re-scan — sectioning already computed the offset from block roles
    so it's stable against content normalization, prepended forward
    buckets, or description first-lines that happen to match the field
    pattern. definition_list entries are single-block and emit no cuts.
    """
    hints: dict = {"chunk_type_hint": meta["entry_chunk_type"]}
    cut_offset = meta.get("stat_block_end_char")
    if cut_offset and cut_offset > 0:
        hints["structure_cuts"] = [
            {
                "kind": "stat_block_end",
                "char_offset": cut_offset,
                "child_chunk_type": "stat_block",
            }
        ]
    return hints


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
    entry_annotation_summary: dict | None = None,
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
    if entry_annotation_summary is not None:
        canonical_report["entry_annotation_summary"] = entry_annotation_summary
    canonical_report_path = canonical_root / "canonical_report.json"
    canonical_report_path.write_text(json.dumps(canonical_report, indent=2) + "\n", encoding="utf-8")
    return extracted_report_path, canonical_report_path


def ingest_source(
    manifest: dict,
    repo_root: Path,
    *,
    force: bool = False,
    limit: int | None = None,
    require_schema_validation: bool = False,
) -> dict:
    if limit is not None and limit <= 0:
        raise ValueError("limit must be a positive integer or None")

    layout = manifest["local_layout"]
    raw_root = resolve_repo_relative_path(repo_root, layout["raw_root"])
    expanded_root = resolve_repo_relative_path(repo_root, layout["expanded_root"])
    extracted_root = resolve_repo_relative_path(repo_root, layout["extracted_root"])
    canonical_root = resolve_repo_relative_path(repo_root, layout["canonical_root"])

    if not force and (extracted_root.exists() or canonical_root.exists()):
        raise FileExistsError(
            "Output directories already exist. Re-run with --force to regenerate extracted/canonical outputs."
        )
    if force:
        remove_directory_if_present(extracted_root, repo_root)
        remove_directory_if_present(canonical_root, repo_root)
    extracted_text_root = extracted_root / "text"
    extracted_ir_root = extracted_root / "ir"
    extracted_text_root.mkdir(parents=True, exist_ok=True)
    extracted_ir_root.mkdir(parents=True, exist_ok=True)
    canonical_root.mkdir(parents=True, exist_ok=True)

    rtf_files = sorted(expanded_root.glob("*.rtf"))
    if limit is not None:
        rtf_files = rtf_files[:limit]

    source_ref = build_source_ref(manifest)
    ingested_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    extraction_records: list[dict] = []
    canonical_records: list[dict] = []
    canonical_docs: list[dict] | None = [] if require_schema_validation else None
    demote_heading_candidate_files = set(manifest.get("fixture_overrides", {}).get("demote_heading_candidate_files", []))
    boilerplate_phrases = set(manifest.get("boilerplate_phrases", []))

    content_types_path = repo_root / "configs" / "content_types.yaml"
    if content_types_path.exists():
        content_types = load_content_types(content_types_path.read_text(encoding="utf-8"))
    else:
        content_types = []

    entry_annotation_summary: dict = {
        "files_with_entries": 0,
        "files_passthrough_no_eligible_type": 0,
        "files_passthrough_no_shape_match": 0,
        "entries_by_type": {},
        "shape_match_failures": [],
    }

    for rtf_path in rtf_files:
        raw_bytes = rtf_path.read_bytes()
        rtf_text = raw_bytes.decode("latin-1", errors="ignore")
        decoded = decode_rtf_text(rtf_text)
        spans = decode_rtf_spans(rtf_text)
        raw_checksum = _sha1_bytes(raw_bytes)
        extracted_checksum = _sha1_text(decoded)

        source_location_base = rtf_path.relative_to(expanded_root).as_posix()
        file_slug = sanitize_identifier(rtf_path.stem)
        extracted_path = extracted_text_root / f"{file_slug}.txt"
        extracted_path.write_text(decoded + "\n", encoding="utf-8")
        extraction_ir = build_extraction_ir(file_name=rtf_path.name, spans=spans)
        if rtf_path.name in demote_heading_candidate_files:
            for block in extraction_ir["blocks"]:
                if block.get("block_type") == "heading_candidate":
                    block["block_type"] = "paragraph"
        annotate_entries(
            extraction_ir["blocks"],
            file_name=rtf_path.name,
            content_types=content_types,
        )

        eligible = eligible_types_for_file(rtf_path.name, content_types)
        file_has_entries = any("entry_index" in b for b in extraction_ir["blocks"])
        if not eligible:
            entry_annotation_summary["files_passthrough_no_eligible_type"] += 1
        elif not file_has_entries:
            entry_annotation_summary["files_passthrough_no_shape_match"] += 1
            for cfg in eligible:
                entry_annotation_summary["shape_match_failures"].append({
                    "file": rtf_path.name,
                    "type": cfg.name,
                    "reason": "no_match",
                })
        else:
            entry_annotation_summary["files_with_entries"] += 1
            type_counts: dict[str, int] = {}
            for b in extraction_ir["blocks"]:
                et = b.get("entry_type")
                if et is not None and b.get("entry_role") in ("title", "definition"):
                    type_counts[et] = type_counts.get(et, 0) + 1
            for type_name, count in type_counts.items():
                entry_annotation_summary["entries_by_type"][type_name] = (
                    entry_annotation_summary["entries_by_type"].get(type_name, 0) + count
                )

        extracted_ir_path = extracted_ir_root / f"{file_slug}.json"
        extracted_ir_path.write_text(json.dumps(extraction_ir, indent=2) + "\n", encoding="utf-8")

        section_candidates = split_sections_from_blocks(rtf_path.stem, extraction_ir["blocks"])
        sections, boundary_decisions = apply_boundary_filters(
            rtf_path.stem,
            rtf_path.name,
            section_candidates,
            boilerplate_phrases=boilerplate_phrases,
        )
        for index, section in enumerate(sections, start=1):
            section_slug = section["section_slug"]
            section_title = section["section_title"]
            source_location = f"{source_location_base}#{index:03d}_{section_slug}"

            meta = section.get("entry_metadata")
            if meta:
                section_path = [meta["entry_category"], meta["entry_title"]]
                document_title = meta["entry_title"]
                locator: dict = {
                    "section_path": section_path,
                    "source_location": source_location,
                    "entry_title": meta["entry_title"],
                }
            else:
                section_path = [rtf_path.stem, section_title]
                document_title = section_title
                locator = {"section_path": section_path, "source_location": source_location}

            document_id = f"{manifest['source_id']}::{file_slug}::{index:03d}_{section_slug}"

            canonical_doc: dict = {
                "document_id": document_id,
                "source_ref": source_ref,
                "locator": locator,
                "content": section["content"],
                "document_title": document_title,
                "source_checksum": raw_checksum,
                "ingested_at": ingested_at,
            }

            if meta:
                canonical_doc["processing_hints"] = _compute_processing_hints(section, meta)

            if canonical_docs is not None:
                canonical_docs.append(canonical_doc)

            canonical_path = canonical_root / f"{file_slug}__{index:03d}_{section_slug}.json"
            canonical_path.write_text(json.dumps(canonical_doc, indent=2) + "\n", encoding="utf-8")
            canonical_records.append(
                {
                    "document_id": document_id,
                    "canonical_path": str(canonical_path.relative_to(repo_root)),
                    "source_checksum": raw_checksum,
                    "section_path": section_path,
                    "source_location": source_location,
                }
            )

        extraction_records.append(
            {
                "file_name": rtf_path.name,
                "source_location": source_location_base,
                "raw_sha1": raw_checksum,
                "extracted_sha1": extracted_checksum,
                "extracted_text_path": str(extracted_path.relative_to(repo_root)),
                "extracted_ir_path": str(extracted_ir_path.relative_to(repo_root)),
                "ir_block_count": len(extraction_ir["blocks"]),
                "section_candidate_count": len(section_candidates),
                "section_count": len(sections),
                "boundary_decisions": boundary_decisions,
            }
        )

    validation_payload = canonical_docs if canonical_docs is not None else []
    validation_result = validate_canonical_docs(validation_payload, repo_root, require_validation=require_schema_validation)
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
        entry_annotation_summary=entry_annotation_summary,
    )
    return {
        "source_id": manifest["source_id"],
        "extracted_root": str(extracted_root),
        "canonical_root": str(canonical_root),
        "documents_written": len(canonical_records),
        "extraction_report": str(extracted_report_path),
        "canonical_report": str(canonical_report_path),
        "schema_validation": validation_result,
    }
