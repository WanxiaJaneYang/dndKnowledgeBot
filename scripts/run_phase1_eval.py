#!/usr/bin/env python3
"""Run the Phase 1 gold-set eval and write JSON + Markdown reports.

Usage:
    python scripts/run_phase1_eval.py
    python scripts/run_phase1_eval.py --top-k 10
    python scripts/run_phase1_eval.py --eval-set evals/phase1_gold.yaml
    python scripts/run_phase1_eval.py --output-dir evals/reports
    python scripts/run_phase1_eval.py --skip-md
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.eval.loader import load_gold_set
from scripts.eval.report import build_report, format_tag_counts, write_json, write_markdown
from scripts.eval.runner import run_case


_DEFAULT_DB = REPO_ROOT / "data" / "index" / "srd_35" / "lexical.db"
_DEFAULT_EVAL_SET = REPO_ROOT / "evals" / "phase1_gold.yaml"
_DEFAULT_OUTPUT_DIR = REPO_ROOT / "evals" / "reports"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Phase 1 gold-set eval and emit JSON + Markdown reports."
    )
    parser.add_argument(
        "--top-k", type=int, default=10, help="Top-k candidates per query (default: 10)"
    )
    parser.add_argument(
        "--eval-set",
        type=Path,
        default=_DEFAULT_EVAL_SET,
        help=f"Path to gold-set YAML (default: {_DEFAULT_EVAL_SET.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {_DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--skip-md",
        action="store_true",
        help="Skip writing the Markdown report (JSON only).",
    )
    parser.add_argument(
        "--db", type=str, default=None, help="Path to lexical.db (default: auto)"
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    db_path = Path(args.db) if args.db else _DEFAULT_DB
    if not db_path.exists():
        print(
            f"Error: lexical.db not found at {db_path}\n"
            "Build the lexical index first (chunks → index).",
            file=sys.stderr,
        )
        sys.exit(1)

    eval_set_path = args.eval_set
    if not eval_set_path.exists():
        print(f"Error: eval set not found at {eval_set_path}", file=sys.stderr)
        sys.exit(1)

    cases = load_gold_set(eval_set_path)
    run_started_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    outcomes = tuple(
        run_case(case, db_path=db_path, top_k=args.top_k) for case in cases
    )

    # Pull dataset_id from the YAML header (falls back to the file stem).
    import yaml as _yaml
    payload = _yaml.safe_load(eval_set_path.read_text(encoding="utf-8"))
    dataset_id = (
        str(payload.get("dataset_id"))
        if isinstance(payload, dict) and payload.get("dataset_id")
        else eval_set_path.stem
    )

    report = build_report(
        outcomes, dataset_id=dataset_id, run_started_at=run_started_at
    )

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "phase1_gold_latest.json"
    write_json(report, json_path)
    if not args.skip_md:
        md_path = output_dir / "phase1_gold_latest.md"
        write_markdown(report, md_path)

    print(format_tag_counts(report))


if __name__ == "__main__":
    main()
