#!/usr/bin/env python3
"""Answer a query from the local chunk index with citations or abstain.

Usage:
    python scripts/answer_question.py "attack of opportunity"
    python scripts/answer_question.py "turn undead" --top-k 5
    python scripts/answer_question.py "fighter bonus feats" --json
    python scripts/answer_question.py "fighter bonus feats" --json-debug
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

from scripts.answer.composer import compose_segments
from scripts.answer.contracts import Abstention, GroundedAnswer
from scripts.answer.pipeline import build_answer, to_debug_json, to_strict_json
from scripts.answer.support_assessor import assess_support
from scripts.retrieval.evidence_pack import EvidencePack, retrieve_evidence


def _print_query_block(pack: EvidencePack) -> None:
    q = pack.query
    print("=" * 72)
    print("QUERY")
    print("=" * 72)
    print(f"  Raw:        {q.raw_query}")
    print(f"  Normalized: {q.normalized_text}")


def _print_grounded_text(result: GroundedAnswer, pack: EvidencePack) -> None:
    print()
    print("=" * 72)
    print(f"ANSWER ({len(result.segments)} segment(s))")
    print("=" * 72)
    for segment in result.segments:
        markers = " ".join(f"[{cid}]" for cid in segment.citation_ids)
        print(f"\n[{segment.segment_id}] ({segment.support_type}) {markers}")
        for line in textwrap.wrap(segment.text, width=78):
            print(f"  {line}")

    print()
    print("=" * 72)
    print(f"CITATIONS ({len(result.citations)})")
    print("=" * 72)
    for citation in result.citations:
        locator = _fmt_locator(citation.locator)
        preview = textwrap.shorten(citation.excerpt, width=140, placeholder="…")
        title = citation.source_ref.get("title", "?")
        print(f"\n  [{citation.citation_id}] {title}")
        print(f"    chunk:   {citation.chunk_id}")
        print(f"    locator: {locator}")
        print(f"    excerpt: {preview}")

    print()
    print("=" * 72)
    print("PIPELINE TRACE")
    print("=" * 72)
    t = pack.trace
    print(f"  Candidates entering shaping: {t.total_candidates}")
    print(f"  Groups formed:               {t.group_count}")
    for gs in t.group_summaries:
        print(f"    [{gs.document_id} / {gs.section_root}] {gs.candidate_count} items")


def _print_abstain_text(result: Abstention) -> None:
    print()
    print("=" * 72)
    print("ABSTAIN")
    print("=" * 72)
    print(f"  Trigger: {result.trigger_code}")
    print(f"  Reason:  {result.reason}")


def _fmt_locator(locator: dict) -> str:
    parts: list[str] = []
    if sp := locator.get("section_path"):
        parts.append(" > ".join(sp))
    if sl := locator.get("source_location"):
        parts.append(sl)
    return " | ".join(parts) if parts else str(locator)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Answer a query from the local chunk index with citations or abstain.",
    )
    parser.add_argument("query", help="The query string to answer")
    parser.add_argument(
        "--top-k", type=int, default=10, help="Number of candidates (default: 10)"
    )
    parser.add_argument(
        "--db", type=str, default=None, help="Path to lexical.db (default: auto)"
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit strict schema JSON (answer_with_citations.schema.json).",
    )
    output_group.add_argument(
        "--json-debug",
        action="store_true",
        dest="json_debug",
        help="Emit extended JSON with a top-level `debug` key (non-schema-valid).",
    )
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None
    effective_db = db_path or (REPO_ROOT / "data" / "index" / "srd_35" / "lexical.db")
    if not effective_db.exists():
        print(
            f"Error: chunk index not found at {effective_db}\n"
            "Build the lexical index first:\n"
            "  python scripts/chunk_srd_35.py",
            file=sys.stderr,
        )
        sys.exit(1)

    pack = retrieve_evidence(args.query, db_path=db_path, top_k=args.top_k)
    result = build_answer(pack)

    if args.json_output:
        print(json.dumps(to_strict_json(result, pack), indent=2, ensure_ascii=False))
        return

    if args.json_debug:
        # Re-run assessor + composer to get the composed segments for debug serialization.
        # build_answer's internal composed tuple isn't exposed; recomposing is cheap and
        # deterministic over the same pack.
        composed: tuple = ()
        if isinstance(result, GroundedAnswer):
            assessment = assess_support(pack)
            if assessment.outcome == "grounded":
                composed = compose_segments(pack)
        print(json.dumps(to_debug_json(result, pack, composed), indent=2, ensure_ascii=False))
        return

    _print_query_block(pack)
    if isinstance(result, Abstention):
        _print_abstain_text(result)
    else:
        _print_grounded_text(result, pack)


if __name__ == "__main__":
    main()
