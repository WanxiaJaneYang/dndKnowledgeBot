#!/usr/bin/env python3
"""Debug CLI for inspecting the retrieval pipeline.

Usage:
    python scripts/retrieve_debug.py "attack of opportunity"
    python scripts/retrieve_debug.py "turn undead" --top-k 5
    python scripts/retrieve_debug.py "fighter hit die" --json
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

# Allow running from repo root without PYTHONPATH.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.retrieval.evidence_pack import EvidencePack, retrieve_evidence


def _print_text(pack: EvidencePack) -> None:
    q = pack.query
    print("=" * 72)
    print("QUERY")
    print("=" * 72)
    print(f"  Raw:        {q.raw_query}")
    print(f"  Normalized: {q.normalized_text}")
    print(f"  Tokens:     {q.tokens}")
    if q.protected_phrases:
        print(f"  Protected:  {q.protected_phrases}")
    if q.aliases_applied:
        print(f"  Aliases:    {q.aliases_applied}")

    print()
    print("=" * 72)
    print("CONSTRAINTS")
    print("=" * 72)
    for key, value in pack.constraints_summary.items():
        print(f"  {key}: {value}")

    print()
    print("=" * 72)
    print("PIPELINE TRACE")
    print("=" * 72)
    t = pack.trace
    print(f"  Candidates entering shaping: {t.total_candidates}")
    print(f"  Groups formed:               {t.group_count}")
    for gs in t.group_summaries:
        print(f"    [{gs.document_id} / {gs.section_root}] {gs.candidate_count} items")

    print()
    print("=" * 72)
    print(f"EVIDENCE ({len(pack.evidence)} items)")
    print("=" * 72)
    for i, item in enumerate(pack.evidence, 1):
        print(f"\n--- Evidence #{i} (rank {item.rank}) ---")
        print(f"  chunk_id:    {item.chunk_id}")
        print(f"  document_id: {item.document_id}")
        print(f"  chunk_type:  {item.chunk_type}")
        print(f"  section:     {item.section_root}")
        print(f"  locator:     {_fmt_locator(item.locator)}")
        print(f"  signals:     {_fmt_signals(item.match_signals)}")
        content_preview = textwrap.shorten(item.content, width=200, placeholder="…")
        print(f"  content:     {content_preview}")


def _fmt_locator(locator: dict) -> str:
    parts = []
    if sp := locator.get("section_path"):
        parts.append(" > ".join(sp))
    if sl := locator.get("source_location"):
        parts.append(sl)
    return " | ".join(parts) if parts else str(locator)


def _fmt_signals(signals: dict) -> str:
    parts = []
    if signals.get("section_path_hit"):
        parts.append("section_path_hit")
    if ep := signals.get("exact_phrase_hits"):
        parts.append(f"exact={ep}")
    if pp := signals.get("protected_phrase_hits"):
        parts.append(f"protected={pp}")
    if tc := signals.get("token_overlap_count"):
        parts.append(f"token_overlap={tc}")
    return ", ".join(parts) if parts else "(none)"


def _to_json(pack: EvidencePack) -> dict:
    return {
        "query": {
            "raw": pack.query.raw_query,
            "normalized": pack.query.normalized_text,
            "tokens": pack.query.tokens,
            "protected_phrases": pack.query.protected_phrases,
            "aliases_applied": pack.query.aliases_applied,
        },
        "constraints": pack.constraints_summary,
        "trace": {
            "total_candidates": pack.trace.total_candidates,
            "group_count": pack.trace.group_count,
            "groups": [
                {
                    "document_id": gs.document_id,
                    "section_root": gs.section_root,
                    "candidate_count": gs.candidate_count,
                }
                for gs in pack.trace.group_summaries
            ],
        },
        "evidence": [
            {
                "rank": item.rank,
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "chunk_type": item.chunk_type,
                "section_root": item.section_root,
                "source_ref": item.source_ref,
                "locator": item.locator,
                "match_signals": dict(item.match_signals),
                "content": item.content,
            }
            for item in pack.evidence
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect retrieval pipeline results for a query."
    )
    parser.add_argument("query", help="The query string to retrieve evidence for")
    parser.add_argument(
        "--top-k", type=int, default=10, help="Number of candidates (default: 10)"
    )
    parser.add_argument(
        "--db", type=str, default=None, help="Path to lexical.db (default: auto)"
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
    )
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None
    effective_db = db_path or (REPO_ROOT / "data" / "index" / "srd_35" / "lexical.db")
    if not effective_db.exists():
        print(
            f"Error: lexical.db not found at {effective_db}\n"
            "Run the indexing pipeline first:\n"
            "  python scripts/chunk_srd_35.py",
            file=sys.stderr,
        )
        sys.exit(1)
    pack = retrieve_evidence(args.query, db_path=db_path, top_k=args.top_k)

    if args.json_output:
        print(json.dumps(_to_json(pack), indent=2, ensure_ascii=False))
    else:
        _print_text(pack)


if __name__ == "__main__":
    main()
