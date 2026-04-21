# Lexical Retriever End-to-End Path

Issue: #43 — Parent: #33

## Goal

Wire the existing lexical retrieval primitives (FTS index, query normalization, match signals, hard filters) into a single `retrieve_lexical()` function that goes from a normalized query to a ranked list of `LexicalCandidate` objects with populated match signals.

## Architecture

A single new module `scripts/retrieval/lexical_retriever.py` with one public function:

```python
def retrieve_lexical(
    query: NormalizedQuery,
    *,
    constraints: RetrievalConstraints | None = None,
    db_path: Path | None = None,
    top_k: int = 10,
) -> list[LexicalCandidate]:
```

It wires together the existing primitives in this order:

1. **Build FTS expression** from `NormalizedQuery` — all tokens double-quoted to prevent FTS5 operator injection, joined with `OR`
2. **Over-fetch** from `_search_raw()` at `top_k * 2`
3. **Apply hard filters** via `RetrievalConstraints.accepts()`
4. **Compute real match signals** via `build_match_signals()` for each candidate
5. **Domain-aware rerank** via `_composite_score()` — combines BM25 with signal boosts (section path hit, exact/protected phrase hits, token overlap)
6. **Truncate** to `top_k` and assign 1-indexed ranks
7. **Return** `list[LexicalCandidate]` with populated signals

The DB path defaults to `data/index/srd_35/lexical.db` relative to repo root.

## FTS Expression Builder

A private helper `_build_fts_expression(query: NormalizedQuery) -> str`:

1. Start with `query.tokens` (already split with protected phrases preserved as multi-word tokens).
2. Double-quote every token to prevent FTS5 operator injection (bare `not`, `and`, etc.).
3. If the full `normalized_text` differs from any single token, prepend it as a quoted phrase so the full query gets phrase-match priority from BM25.
4. Join all parts with `OR`.

Example: query `"fighter hit points"` with protected phrase `"hit points"` and tokens `["fighter", "hit points"]` produces:

```
"fighter hit points" OR "fighter" OR "hit points"
```

Full-phrase matches rank highest via BM25, partial matches still recalled.

## Match Signal Hydration

After FTS returns raw candidates, each candidate is hydrated with real match signals via `build_match_signals(query, chunk_dict, section_path_text)`.

The existing `search_chunk_index()` returns `LexicalCandidate` with empty placeholder signals. Rather than changing that public API, the retriever uses a package-private variant that returns raw row data (including `content` and `section_path_text`) alongside the candidate fields. The retriever then constructs a minimal chunk dict from the row data and calls `build_match_signals()`.

## Domain-Aware Reranking

After match signals are computed, candidates are sorted by a composite score via `_composite_score(raw_score, signals)`. BM25 is lower-is-better, so boosts subtract from the score:

- Section path hit: -2.0
- Exact phrase hit: -1.5 per hit
- Protected phrase hit: -1.0 per hit
- Token overlap: -0.1 per overlapping term

This keeps BM25 as the primary signal while letting domain-aware match signals promote candidates that are structurally or terminologically relevant.

## Hard Filter Strategy

Post-retrieval filtering with over-fetch. The retriever requests `top_k * 2` from FTS, then runs `RetrievalConstraints.accepts()` on each candidate to filter, then truncates to `top_k`.

This is appropriate for Phase 1: the corpus is single-edition SRD-only, so nearly all chunks pass. Over-fetching is cheap, keeps FTS query construction simple, and the post-filter safety net is already built. FTS column filters can be added later if multi-source support requires it.

## Files Changed

New:
- `scripts/retrieval/lexical_retriever.py` — `retrieve_lexical()` and `_build_fts_expression()`

Modified:
- `scripts/retrieval/__init__.py` — export `retrieve_lexical`
- `scripts/retrieval/lexical_index.py` — add package-private `_search_chunk_index_raw()` that returns row data for signal hydration

New tests:
- `tests/test_lexical_retriever.py`

## Test Plan

- FTS expression builder produces correct expressions for single-token, multi-token, and protected-phrase queries
- `retrieve_lexical()` returns `LexicalCandidate` objects with populated (non-placeholder) match signals
- Hard filters reject candidates that don't match constraints
- Over-fetch ensures `top_k` results survive filtering when some candidates are rejected
- Real corpus recall: `turn undead`, `attack of opportunity`, `fighter bonus feats` return expected chunks
- Empty query or no-match query returns empty list
- Default DB path resolves correctly

## Out of Scope

- Semantic or vector retrieval
- Reranking model
- Hierarchical candidate shaping (#44)
- Full domain-aware scoring model beyond lightweight composite reranking (#47)
- Candidate deduplication (#34)
