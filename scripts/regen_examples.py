#!/usr/bin/env python3
"""Regenerate example artifacts for the evidence pack and answer contracts.

Builds a tiny temporary chunk index in-memory, runs the real retrieval and
answer pipelines against it, and overwrites:

    examples/evidence_pack.example.json
    examples/answer_with_citations.example.json

Usage:
    python scripts/regen_examples.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.answer.pipeline import build_answer, to_strict_json
from scripts.retrieval.evidence_pack import retrieve_evidence
from scripts.retrieval.lexical_index import build_chunk_index
from scripts.retrieve_debug import _to_json as pack_to_json


_EXAMPLES_DIR = REPO_ROOT / "examples"


_CHUNKS: list[dict] = [
    {
        "chunk_id": "srd_35::combat::attack_of_opportunity::chunk_1",
        "document_id": "srd_35::combat",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["Combat", "Attack of Opportunity"],
            "entry_title": "Attack of Opportunity",
            "source_location": "Combat.rtf > Attack of Opportunity > paragraph 1",
        },
        "chunk_type": "rule_section",
        "content": (
            "Sometimes a combatant in a melee lets her guard down or "
            "takes a reckless action. In this case, combatants near her "
            "can take advantage of her lapse in defense to attack her "
            "for free. These free attacks are called attacks of "
            "opportunity."
        ),
    },
    {
        "chunk_id": "srd_35::combat::attack_of_opportunity::chunk_2",
        "document_id": "srd_35::combat",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["Combat", "Attack of Opportunity", "Threatened Squares"],
            "entry_title": "Threatened Squares",
            "source_location": "Combat.rtf > Threatened Squares",
        },
        "chunk_type": "rule_section",
        "content": (
            "You threaten all squares into which you can make a melee "
            "attack, even when it is not your turn. Generally, that "
            "means everything in all squares adjacent to your space."
        ),
    },
    {
        "chunk_id": "srd_35::spells::fireball::chunk_1",
        "document_id": "srd_35::spells",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["Spells", "Fireball"],
            "entry_title": "Fireball",
            "source_location": "SpellsD-F.rtf > Fireball",
        },
        "chunk_type": "rule_section",
        "content": (
            "A fireball spell generates a searing explosion of flame "
            "that detonates with a low roar. It deals 1d6 points of "
            "fire damage per caster level."
        ),
    },
]


def _write_pack_example(pack, out_path: Path) -> None:
    payload = pack_to_json(pack)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_answer_example(result, pack, out_path: Path) -> None:
    payload = to_strict_json(result, pack)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    _EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    # ignore_cleanup_errors: on Windows the SQLite file handle may linger briefly
    # after the sqlite3 module's context manager exits, causing TemporaryDirectory
    # cleanup to race. The example content is already written by then.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_str:
        tmp_dir = Path(tmp_str)
        chunk_paths: list[Path] = []
        for chunk in _CHUNKS:
            chunk_path = tmp_dir / f"{chunk['chunk_id'].replace('::', '__')}.json"
            chunk_path.write_text(
                json.dumps(chunk, ensure_ascii=False), encoding="utf-8"
            )
            chunk_paths.append(chunk_path)
        db_path = tmp_dir / "lexical.db"
        build_chunk_index(db_path, chunk_paths)

        pack = retrieve_evidence(
            "attack of opportunity", db_path=db_path, top_k=10
        )
        result = build_answer(pack)

    pack_out = _EXAMPLES_DIR / "evidence_pack.example.json"
    answer_out = _EXAMPLES_DIR / "answer_with_citations.example.json"
    _write_pack_example(pack, pack_out)
    _write_answer_example(result, pack, answer_out)

    print(f"wrote {pack_out}")
    print(f"wrote {answer_out}")


if __name__ == "__main__":
    main()
