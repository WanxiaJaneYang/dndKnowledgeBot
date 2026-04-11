from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_MANIFEST = Path("configs/bootstrap_sources/srd_35.manifest.json")

INGESTION_NOTES = [
    "Phase-1 ingestion spike: one canonical document per SRD RTF file.",
    "Locator policy follows source-native file names with section_path and source_location.",
]

EXTRACTION_CAVEATS = [
    "RTF control words are stripped heuristically and may lose some formatting semantics.",
    "Table-heavy sections may flatten cell structure and should be refined in later ingestion iterations.",
]


def load_manifest(manifest_path: Path) -> dict:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _resolve_repo_relative_path(repo_root: Path, manifest_path: str) -> Path:
    resolved_repo_root = repo_root.resolve()
    resolved_path = (resolved_repo_root / manifest_path).resolve()
    if resolved_repo_root not in resolved_path.parents and resolved_path != resolved_repo_root:
        raise ValueError(f"Manifest path escapes repository root: {manifest_path}")
    return resolved_path


def _remove_directory_if_present(path: Path, repo_root: Path) -> None:
    if not path.exists():
        return

    resolved_repo_root = repo_root.resolve()
    resolved_path = path.resolve()
    if resolved_path == resolved_repo_root:
        raise RuntimeError(f"Refusing to remove repository root: {resolved_path}")
    if resolved_repo_root not in resolved_path.parents:
        raise RuntimeError(f"Refusing to remove path outside repo root: {resolved_path}")

    shutil.rmtree(resolved_path)


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


def decode_rtf_text(rtf_text: str) -> str:
    output: list[str] = []
    i = 0
    uc_skip = 1
    pending_skip = 0
    stack: list[tuple[int, int]] = []
    length = len(rtf_text)

    while i < length:
        char = rtf_text[i]

        if char == "{":
            stack.append((uc_skip, pending_skip))
            i += 1
            continue

        if char == "}":
            if stack:
                uc_skip, pending_skip = stack.pop()
            i += 1
            continue

        if pending_skip > 0:
            pending_skip -= 1
            i += 1
            continue

        if char != "\\":
            output.append(char)
            i += 1
            continue

        i += 1
        if i >= length:
            break

        control_start = rtf_text[i]
        if control_start in "{}\\":
            output.append(control_start)
            i += 1
            continue

        if control_start == "'":
            if i + 2 < length:
                hex_value = rtf_text[i + 1 : i + 3]
                try:
                    output.append(bytes.fromhex(hex_value).decode("cp1252"))
                except ValueError:
                    pass
                i += 3
                continue

        if not control_start.isalpha():
            if control_start == "~":
                output.append(" ")
            elif control_start in {"-", "_"}:
                output.append("-")
            elif control_start in {"\n", "\r"}:
                pass
            i += 1
            continue

        start = i
        while i < length and rtf_text[i].isalpha():
            i += 1
        word = rtf_text[start:i]

        sign = 1
        if i < length and rtf_text[i] in {"+", "-"}:
            if rtf_text[i] == "-":
                sign = -1
            i += 1

        num_start = i
        while i < length and rtf_text[i].isdigit():
            i += 1
        numeric: int | None = None
        if i > num_start:
            numeric = int(rtf_text[num_start:i]) * sign

        if i < length and rtf_text[i] == " ":
            i += 1

        if word == "uc" and numeric is not None:
            uc_skip = max(numeric, 0)
            continue
        if word == "u" and numeric is not None:
            codepoint = numeric if numeric >= 0 else numeric + 65536
            try:
                output.append(chr(codepoint))
            except ValueError:
                pass
            pending_skip = uc_skip
            continue

        if word in {"par", "line", "row"}:
            output.append("\n")
            continue
        if word == "tab":
            output.append("\t")
            continue
        if word == "cell":
            output.append(" | ")
            continue
        if word in {"emdash"}:
            output.append("--")
            continue
        if word in {"endash"}:
            output.append("-")
            continue
        if word in {"lquote", "rquote"}:
            output.append("'")
            continue
        if word in {"ldblquote", "rdblquote"}:
            output.append('"')
            continue

    text = "".join(output).replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def build_source_ref(manifest: dict) -> dict:
    return {
        "source_id": manifest["source_id"],
        "title": manifest["title"],
        "edition": manifest["edition"],
        "source_type": manifest["source_type"],
        "authority_level": manifest["authority_level"],
    }


def ingest_source(
    manifest: dict,
    repo_root: Path,
    *,
    force: bool = False,
    limit: int | None = None,
) -> dict:
    layout = manifest["local_layout"]
    raw_root = _resolve_repo_relative_path(repo_root, layout["raw_root"])
    expanded_root = _resolve_repo_relative_path(repo_root, layout["expanded_root"])
    extracted_root = _resolve_repo_relative_path(repo_root, layout["extracted_root"])
    canonical_root = _resolve_repo_relative_path(repo_root, layout["canonical_root"])

    if force:
        _remove_directory_if_present(extracted_root, repo_root)
        _remove_directory_if_present(canonical_root, repo_root)

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
            "locator": {
                "section_path": section_path,
                "source_location": source_location,
            },
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

    return {
        "source_id": manifest["source_id"],
        "extracted_root": str(extracted_root),
        "canonical_root": str(canonical_root),
        "documents_written": len(canonical_records),
        "extraction_report": str(extracted_report_path),
        "canonical_report": str(canonical_report_path),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the first SRD 3.5e ingestion spike (raw -> extracted -> canonical).")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the committed srd_35 manifest JSON.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root used to resolve local data paths.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate extracted/canonical outputs from scratch.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional file limit for quick local spikes.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else (repo_root / args.manifest).resolve()
    manifest = load_manifest(manifest_path)
    result = ingest_source(
        manifest,
        repo_root,
        force=args.force,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Ingested {result['source_id']} into:")
        print(f"- extracted: {result['extracted_root']}")
        print(f"- canonical: {result['canonical_root']}")
        print(f"Documents written: {result['documents_written']}")
        print(f"Extraction report: {result['extraction_report']}")
        print(f"Canonical report: {result['canonical_report']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
