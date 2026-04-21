"""End-to-end lexical retriever for Phase 1."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .contracts import LexicalCandidate, MatchSignals, NormalizedQuery
from .filters import RetrievalConstraints, build_constraints
from .lexical_index import _search_raw
from .match_signals import build_match_signals

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "index" / "srd_35" / "lexical.db"

# Signal boost weights (subtracted from BM25 score, which is lower-is-better).
_SECTION_PATH_BOOST = 2.0
_PROTECTED_PHRASE_BOOST = 1.0
_EXACT_PHRASE_BOOST = 1.5
_TOKEN_OVERLAP_BOOST = 0.1


def _build_fts_expression(query: NormalizedQuery) -> str:
    """Build an FTS5 MATCH expression from a normalized query.

    All tokens are double-quoted to prevent FTS5 operator injection
    (e.g. a bare ``not`` or ``and`` would be parsed as boolean operators).
    """
    if not query.tokens:
        return ""

    parts: list[str] = [f'"{token}"' for token in query.tokens]

    # Prepend the full normalized text as a quoted phrase when it differs
    # from any single token — gives BM25 full-phrase match priority.
    if len(query.tokens) > 1:
        parts.insert(0, f'"{query.normalized_text}"')

    return " OR ".join(parts)


def _composite_score(raw_score: float, signals: MatchSignals) -> float:
    """Combine BM25 raw score with match-signal boosts.

    BM25 scores are lower-is-better (negative), so we subtract boosts
    to promote candidates with stronger domain signals.
    """
    score = raw_score
    if signals["section_path_hit"]:
        score -= _SECTION_PATH_BOOST
    score -= len(signals["exact_phrase_hits"]) * _EXACT_PHRASE_BOOST
    score -= len(signals["protected_phrase_hits"]) * _PROTECTED_PHRASE_BOOST
    score -= signals["token_overlap_count"] * _TOKEN_OVERLAP_BOOST
    return score


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

    candidates.sort(key=lambda c: _composite_score(c.raw_score, c.match_signals))
    return [
        replace(c, rank=rank)
        for rank, c in enumerate(candidates[:top_k], start=1)
    ]
