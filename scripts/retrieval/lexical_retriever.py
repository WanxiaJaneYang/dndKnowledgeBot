"""End-to-end lexical retriever for Phase 1."""
from __future__ import annotations

from pathlib import Path

from .contracts import LexicalCandidate, NormalizedQuery
from .filters import RetrievalConstraints, build_constraints
from .lexical_index import _search_raw
from .match_signals import build_match_signals

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "index" / "srd_35" / "lexical.db"


def _build_fts_expression(query: NormalizedQuery) -> str:
    """Build an FTS5 MATCH expression from a normalized query."""
    if not query.tokens:
        return ""

    protected_set = set(query.protected_phrases)
    parts: list[str] = []

    for token in query.tokens:
        if token in protected_set:
            parts.append(f'"{token}"')
        else:
            parts.append(token)

    # Prepend the full normalized text as a quoted phrase when it differs
    # from any single token — gives BM25 full-phrase match priority.
    if len(query.tokens) > 1:
        full_phrase = f'"{query.normalized_text}"'
        parts.insert(0, full_phrase)

    return " OR ".join(parts)


def retrieve_lexical(
    query: NormalizedQuery,
    *,
    constraints: RetrievalConstraints | None = None,
    db_path: Path | None = None,
    top_k: int = 10,
) -> list[LexicalCandidate]:
    """Run end-to-end lexical retrieval from normalized query to ranked candidates."""
    fts_expression = _build_fts_expression(query)
    if not fts_expression:
        return []

    if constraints is None:
        constraints = build_constraints()
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    raw_rows = _search_raw(db_path, fts_expression, top_k=top_k * 2)

    candidates: list[LexicalCandidate] = []
    for row in raw_rows:
        if not constraints.accepts(row):
            continue

        chunk_dict = {"content": row["content"], "source_ref": row["source_ref"]}
        signals = build_match_signals(query, chunk_dict, row["section_path_text"])

        candidates.append(
            LexicalCandidate(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                rank=0,
                raw_score=row["raw_score"],
                score_direction="lower_is_better",
                chunk_type=row["chunk_type"],
                source_ref=row["source_ref"],
                locator=row["locator"],
                match_signals=signals,
            )
        )

    truncated = candidates[:top_k]
    return [
        LexicalCandidate(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            rank=rank,
            raw_score=c.raw_score,
            score_direction=c.score_direction,
            chunk_type=c.chunk_type,
            source_ref=c.source_ref,
            locator=c.locator,
            match_signals=c.match_signals,
        )
        for rank, c in enumerate(truncated, start=1)
    ]
