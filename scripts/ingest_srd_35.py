from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ingest_srd35 import DEFAULT_MANIFEST, decode_rtf_text, ingest_source, load_manifest
else:
    from scripts.ingest_srd35 import DEFAULT_MANIFEST, decode_rtf_text, ingest_source, load_manifest


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
    parser.add_argument(
        "--require-schema-validation",
        action="store_true",
        help="Fail ingestion if canonical JSON cannot be validated against canonical_document.schema.json.",
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
        require_schema_validation=args.require_schema_validation,
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
