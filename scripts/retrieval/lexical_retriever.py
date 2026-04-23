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

# Chunk-type prior: rule-bearing types get a boost, generic/unknown get none.
# Keys must match the chunk_type enum in schemas/chunk.schema.json — a guard
# test in test_lexical_retriever.py enforces this at CI time.
#
# Ordering rationale:
#   rule_section (1.0) — top-level rule definitions, highest signal for rule lookups
#   class_feature (0.8) — named mechanical features, almost always what a
#       class-related query wants; ranked above individual entries because they
#       carry more context per chunk
#   feat/skill/spell/condition_entry (0.6) — discrete catalogue entries
#   subsection (0.5) — general rule prose, common but less targeted
#   errata_note (0.4) — authoritative corrections
#   table, faq_note, glossary_entry (0.3) — supporting reference material
#   paragraph_group (0.2) — contextual prose groupings
#   example, sidebar (0.1) — illustrative, rarely the primary answer
#   generic (0.0) — no signal (e.g. legal/license boilerplate)
#
# Most types beyond rule_section/subsection/generic are forward-looking; the
# current Phase 1 classifier mostly emits those three.
_CHUNK_TYPE_PRIOR: dict[str, float] = {
    "rule_section": 1.0,
    "class_feature": 0.8,
    "feat_entry": 0.6,
    "skill_entry": 0.6,
    "spell_entry": 0.6,
    "condition_entry": 0.6,
    "subsection": 0.5,
    "errata_note": 0.4,
    "table": 0.3,
    "faq_note": 0.3,
    "glossary_entry": 0.3,
    "paragraph_group": 0.2,
    "example": 0.1,
    "sidebar": 0.1,
    "generic": 0.0,
}


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


def _composite_score(
    raw_score: float, signals: MatchSignals, chunk_type: str = ""
) -> float:
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
    score -= _CHUNK_TYPE_PRIOR.get(chunk_type, 0.0)
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
                parent_chunk_id=row.get("parent_chunk_id"),
                previous_chunk_id=row.get("previous_chunk_id"),
                next_chunk_id=row.get("next_chunk_id"),
            )
        )

    candidates.sort(
        key=lambda c: _composite_score(c.raw_score, c.match_signals, c.chunk_type)
    )
    return [
        replace(c, rank=rank)
        for rank, c in enumerate(candidates[:top_k], start=1)
    ]
