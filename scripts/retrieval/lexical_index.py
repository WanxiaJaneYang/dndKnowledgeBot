"""SQLite index helpers for lexical retrieval."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .contracts import LexicalCandidate


def build_chunk_index(db_path: Path, chunk_paths: Iterable[Path]) -> None:
    """Create a lexical index database from chunk JSON files."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        _create_schema(connection)
        _replace_rows(connection, chunk_paths)
        connection.commit()


def search_chunk_index(db_path: Path, query_text: str, *, top_k: int = 5) -> list[LexicalCandidate]:
    """Run an FTS query and return hydrated top-k rows.

    ``query_text`` must already be a valid SQLite FTS5 MATCH expression.
    This helper does not sanitize raw user input.
    """
    if top_k <= 0:
        return []
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                chunk_metadata.chunk_id,
                chunk_metadata.document_id,
                chunk_metadata.section_path_text,
                chunk_metadata.chunk_type,
                chunk_metadata.source_ref_json,
                chunk_metadata.locator_json,
                chunk_metadata.content,
                bm25(chunks_fts) AS raw_score
            FROM chunks_fts
            JOIN chunk_metadata ON chunk_metadata.chunk_id = chunks_fts.chunk_id
            WHERE chunks_fts MATCH ?
            ORDER BY raw_score ASC
            LIMIT ?
            """,
            (query_text, top_k),
        ).fetchall()

    hydrated: list[LexicalCandidate] = []
    for rank, row in enumerate(rows, start=1):
        hydrated.append(
            LexicalCandidate(
                chunk_id=row[0],
                document_id=row[1],
                rank=rank,
                raw_score=float(row[7]),
                score_direction="lower_is_better",
                chunk_type=row[3],
                source_ref=json.loads(row[4]),
                locator=json.loads(row[5]),
                match_signals={
                    "exact_phrase_hits": [],
                    "protected_phrase_hits": [],
                    "section_path_hit": False,
                    "token_overlap_count": 0,
                },
            )
        )
    return hydrated


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.execute("DROP TABLE IF EXISTS chunk_metadata")
    connection.execute("DROP TABLE IF EXISTS chunks_fts")
    try:
        connection.execute(
            """
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                chunk_id UNINDEXED,
                document_id UNINDEXED,
                content,
                section_path_text,
                chunk_type,
                source_id,
                edition,
                source_layer
            )
            """
        )
    except sqlite3.OperationalError as exc:
        raise RuntimeError("SQLite FTS5 support is required for lexical retrieval.") from exc

    connection.execute(
        """
        CREATE TABLE chunk_metadata (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            section_path_text TEXT NOT NULL,
            chunk_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            edition TEXT NOT NULL,
            source_layer TEXT NOT NULL,
            source_ref_json TEXT NOT NULL,
            locator_json TEXT NOT NULL,
            content TEXT NOT NULL
        )
        """
    )


def _replace_rows(connection: sqlite3.Connection, chunk_paths: Iterable[Path]) -> None:
    for chunk_path in chunk_paths:
        chunk = json.loads(Path(chunk_path).read_text(encoding="utf-8"))
        locator = chunk["locator"]
        source_ref = chunk["source_ref"]
        section_path = locator["section_path"]
        section_path_text = " ".join(section_path)
        source_layer = source_ref["source_type"]

        connection.execute(
            """
            INSERT INTO chunk_metadata (
                chunk_id,
                document_id,
                section_path_text,
                chunk_type,
                source_id,
                edition,
                source_layer,
                source_ref_json,
                locator_json,
                content
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk["chunk_id"],
                chunk["document_id"],
                section_path_text,
                chunk["chunk_type"],
                source_ref["source_id"],
                source_ref["edition"],
                source_layer,
                json.dumps(source_ref, ensure_ascii=True, sort_keys=True),
                json.dumps(locator, ensure_ascii=True, sort_keys=True),
                chunk["content"],
            ),
        )
        connection.execute(
            """
            INSERT INTO chunks_fts (
                chunk_id,
                document_id,
                content,
                section_path_text,
                chunk_type,
                source_id,
                edition,
                source_layer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk["chunk_id"],
                chunk["document_id"],
                chunk["content"],
                section_path_text,
                chunk["chunk_type"],
                source_ref["source_id"],
                source_ref["edition"],
                source_layer,
            ),
        )
