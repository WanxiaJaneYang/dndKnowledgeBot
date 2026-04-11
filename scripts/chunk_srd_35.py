"""CLI entry point: produce baseline chunks from canonical SRD 3.5e documents.

Usage:
    python scripts/chunk_srd_35.py
    python scripts/chunk_srd_35.py --force
    python scripts/chunk_srd_35.py --require-schema-validation
    python scripts/chunk_srd_35.py --canonical-root data/canonical/srd_35 --output data/chunks/srd_35
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from chunker import chunk_source
else:
    from scripts.chunker import chunk_source

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CANONICAL_ROOT = _REPO_ROOT / "data" / "canonical" / "srd_35"
_DEFAULT_OUTPUT_ROOT = _REPO_ROOT / "data" / "chunks" / "srd_35"
_SOURCE_ID = "srd_35"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Produce baseline chunks from canonical SRD 3.5e documents."
    )
    parser.add_argument(
        "--canonical-root",
        type=Path,
        default=_DEFAULT_CANONICAL_ROOT,
        help="Directory containing canonical document JSON files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT_ROOT,
        help="Directory to write chunk JSON files.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_REPO_ROOT,
        help="Repository root (used for schema resolution and relative paths in reports).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing chunk output directory.",
    )
    parser.add_argument(
        "--require-schema-validation",
        action="store_true",
        help="Fail if any chunk does not validate against chunk.schema.json.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print result as JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    canonical_root = args.canonical_root if args.canonical_root.is_absolute() else (repo_root / args.canonical_root)
    output_root = args.output if args.output.is_absolute() else (repo_root / args.output)

    result = chunk_source(
        canonical_root=canonical_root,
        output_root=output_root,
        repo_root=repo_root,
        source_id=_SOURCE_ID,
        force=args.force,
        require_schema_validation=args.require_schema_validation,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Chunked {result['source_id']}:")
        print(f"  canonical root : {result['canonical_root']}")
        print(f"  output root    : {result['output_root']}")
        print(f"  chunks written : {result['chunks_written']}")
        print(f"  chunk report   : {result['chunk_report']}")
        validation = result["schema_validation"]
        if validation["enabled"]:
            print(f"  schema valid   : {validation['validated_count']} chunks")
        else:
            print("  schema valid   : skipped (pass --require-schema-validation to enable)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
