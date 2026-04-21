"""SQLite index helpers for lexical retrieval."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from .contracts import LexicalCandidate


def build_chunk_index(db_path: Path, chunk_paths: Iterable[Path]) -> None:
    """Create a lexical index database from chunk JSON files."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp_db_path = db_path.with_name(f"{db_path.name}.{uuid4().hex}.tmp")
    connection: sqlite3.Connection | None = None

    try:
        connection = sqlite3.connect(temp_db_path)
        _create_schema(connection)
        _replace_rows(connection, chunk_paths)
        connection.commit()
        connection.close()
        connection = None
        temp_db_path.replace(db_path)
    except Exception:
        if connection is not None:
            connection.close()
        temp_db_path.unlink(missing_ok=True)
        raise


def search_chunk_index(db_path: Path, query_text: str, *, top_k: int = 5) -> list[LexicalCandidate]:
    """Run an FTS query and return hydrated top-k rows.

    ``query_text`` must already be a valid SQLite FTS5 MATCH expression.
    This helper does not sanitize raw user input.
    """
    raw = _search_raw(db_path, query_text, top_k=top_k)
    return [
        LexicalCandidate(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            rank=rank,
            raw_score=row["raw_score"],
            score_direction="lower_is_better",
            chunk_type=row["chunk_type"],
            source_ref=row["source_ref"],
            locator=row["locator"],
            match_signals={
                "exact_phrase_hits": [],
                "protected_phrase_hits": [],
                "section_path_hit": False,
                "token_overlap_count": 0,
            },
        )
        for rank, row in enumerate(raw, start=1)
    ]


def _search_raw(db_path: Path, query_text: str, *, top_k: int = 5) -> list[dict]:
    """Return raw row dicts for signal hydration. Package-private."""
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
                bm25(chunks_fts) AS raw_score,
                chunk_metadata.section_path_json,
                chunk_metadata.heading_level,
                chunk_metadata.parent_chunk_id,
                chunk_metadata.previous_chunk_id,
                chunk_metadata.next_chunk_id
            FROM chunks_fts
            JOIN chunk_metadata ON chunk_metadata.chunk_id = chunks_fts.chunk_id
            WHERE chunks_fts MATCH ?
            ORDER BY raw_score ASC
            LIMIT ?
            """,
            (query_text, top_k),
        ).fetchall()

    return [
        {
            "chunk_id": row[0],
            "document_id": row[1],
            "section_path_text": row[2],
            "chunk_type": row[3],
            "source_ref": json.loads(row[4]),
            "locator": json.loads(row[5]),
            "content": row[6],
            "raw_score": float(row[7]),
            "section_path": json.loads(row[8]),
            "heading_level": row[9],
            "parent_chunk_id": row[10],
            "previous_chunk_id": row[11],
            "next_chunk_id": row[12],
        }
        for row in rows
    ]


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
            section_path_json TEXT NOT NULL,
            heading_level INTEGER NOT NULL,
            chunk_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            edition TEXT NOT NULL,
            source_layer TEXT NOT NULL,
            source_ref_json TEXT NOT NULL,
            locator_json TEXT NOT NULL,
            content TEXT NOT NULL,
            parent_chunk_id TEXT,
            previous_chunk_id TEXT,
            next_chunk_id TEXT
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
                section_path_json,
                heading_level,
                chunk_type,
                source_id,
                edition,
                source_layer,
                source_ref_json,
                locator_json,
                content,
                parent_chunk_id,
                previous_chunk_id,
                next_chunk_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk["chunk_id"],
                chunk["document_id"],
                section_path_text,
                json.dumps(section_path, ensure_ascii=True),
                len(section_path),
                chunk["chunk_type"],
                source_ref["source_id"],
                source_ref["edition"],
                source_layer,
                json.dumps(source_ref, ensure_ascii=True, sort_keys=True),
                json.dumps(locator, ensure_ascii=True, sort_keys=True),
                chunk["content"],
                chunk.get("parent_chunk_id"),
                chunk.get("previous_chunk_id"),
                chunk.get("next_chunk_id"),
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
