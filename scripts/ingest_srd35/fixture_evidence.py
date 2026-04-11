from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from .pipeline import ingest_source


def _build_fixture_manifest() -> dict:
    return {
        "source_id": "srd_35_fixture",
        "title": "SRD 3.5 Fixture Corpus (Real Source Files)",
        "edition": "3.5e",
        "source_type": "srd",
        "authority_level": "official_reference",
        "local_layout": {
            "raw_root": "data/raw/srd_35_fixture",
            "expanded_root": "data/raw/srd_35_fixture/rtf",
            "extracted_root": "data/extracted/srd_35_fixture",
            "canonical_root": "data/canonical/srd_35_fixture",
        },
        "fixture_overrides": {
            "demote_heading_candidate_files": [
                "DivineMinions.rtf",
            ]
        },
    }


def _normalize_canonical(doc: dict) -> dict:
    normalized = dict(doc)
    normalized.pop("ingested_at", None)
    return normalized


def run_fixture_ingestion(repo_root: Path) -> dict:
    fixture_root = repo_root / "tests" / "fixtures" / "srd_35"
    if not fixture_root.exists():
        raise FileNotFoundError(f"Fixture root not found: {fixture_root}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        expanded_root = tmp_root / "data" / "raw" / "srd_35_fixture" / "rtf"
        expanded_root.mkdir(parents=True, exist_ok=True)

        for src in sorted(fixture_root.glob("*.rtf")):
            shutil.copy2(src, expanded_root / src.name)

        manifest = _build_fixture_manifest()
        result = ingest_source(manifest, tmp_root, force=True, require_schema_validation=False)

        extracted_dir = Path(result["extracted_root"]) / "text"
        extracted_ir_dir = Path(result["extracted_root"]) / "ir"
        canonical_dir = Path(result["canonical_root"])
        extracted_report = json.loads(Path(result["extraction_report"]).read_text(encoding="utf-8"))
        canonical_report = json.loads(Path(result["canonical_report"]).read_text(encoding="utf-8"))

        extracted = {
            path.name: path.read_text(encoding="utf-8")
            for path in sorted(extracted_dir.glob("*.txt"))
        }
        extracted_ir = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(extracted_ir_dir.glob("*.json"))
        }
        canonical = {
            path.name: _normalize_canonical(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(canonical_dir.glob("*.json"))
            if path.name != "canonical_report.json"
        }

        return {
            "extracted": extracted,
            "extracted_ir": extracted_ir,
            "canonical": canonical,
            "extraction_report": extracted_report,
            "canonical_report": canonical_report,
        }


def write_golden_outputs(repo_root: Path, evidence: dict) -> None:
    expected_root = repo_root / "tests" / "fixtures" / "expected"
    extracted_root = expected_root / "extracted"
    extracted_ir_root = expected_root / "extracted_ir"
    canonical_root = expected_root / "canonical"
    extracted_root.mkdir(parents=True, exist_ok=True)
    extracted_ir_root.mkdir(parents=True, exist_ok=True)
    canonical_root.mkdir(parents=True, exist_ok=True)

    for path in extracted_root.glob("*"):
        if path.is_file():
            path.unlink()
    for path in extracted_ir_root.glob("*"):
        if path.is_file():
            path.unlink()
    for path in canonical_root.glob("*"):
        if path.is_file():
            path.unlink()

    for name, text in evidence["extracted"].items():
        (extracted_root / name).write_text(text, encoding="utf-8")

    for name, payload in evidence["extracted_ir"].items():
        (extracted_ir_root / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    for name, payload in evidence["canonical"].items():
        (canonical_root / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_golden_outputs(repo_root: Path) -> dict:
    expected_root = repo_root / "tests" / "fixtures" / "expected"
    extracted_root = expected_root / "extracted"
    extracted_ir_root = expected_root / "extracted_ir"
    canonical_root = expected_root / "canonical"

    extracted = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(extracted_root.glob("*.txt"))
    }
    extracted_ir = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(extracted_ir_root.glob("*.json"))
    }
    canonical = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(canonical_root.glob("*.json"))
    }
    return {"extracted": extracted, "extracted_ir": extracted_ir, "canonical": canonical}
