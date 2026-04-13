# Lexical Retrieval Baseline Design

**Date:** 2026-04-12
**Issue:** #33

## 1. Goal

Implement the Phase 1 lexical-first candidate generator over the chunk corpus using SQLite FTS5 with BM25 ranking. The output should be a small, inspectable candidate set that preserves chunk identity, rank, score, and simple match signals without taking on consolidation, hybrid retrieval, or answer-facing evidence packaging.

## 2. Scope and Non-Goals

### In Scope

- Consume normalized query output from Issue #31.
- Consume hard retrieval constraints from Issue #32.
- Build and query a local SQLite FTS5 index over chunk content plus selected retrieval metadata.
- Return top-k lexical candidates with stable ranking metadata and lightweight match signals.
- Cover core rules queries such as `fighter hit die`, `attack of opportunity`, `turn undead`, and `what are bonus feats` in deterministic tests.

### Non-Goals

- Semantic or vector retrieval.
- Candidate consolidation or near-duplicate collapse.
- Adjacent chunk merge or section grouping.
- Final evidence-pack selection or retrieval CLI formatting beyond what later issues need.
- Pulling normalization or filtering logic into Issue #33 internals.

## 3. Proposed Design

### Minimal Data Flow

```text
User Question
  ->
NormalizedQuery          (#31)
  +
RetrievalConstraints     (#32)
  ->
LexicalRetriever
  ->
SQLite FTS5 Index
  ->
Raw Candidates (top-k)
  ->
Issue #33 output contract
```

The retrieval stage remains narrow by design. Query normalization and boundary filtering happen before scoring. Issue #33 only performs lexical search, ranking, and signal attachment.

### Module Layout

```text
scripts/
  retrieval/
    __init__.py
    contracts.py
    lexical_index.py
    lexical_retriever.py
    match_signals.py

tests/
  test_lexical_retrieval.py
```

#### `contracts.py`

Owns retrieval-facing dataclasses and stable output contracts. It should define typed objects for normalized query input, lexical candidate output, and any index-row helper shape needed internally.

#### `lexical_index.py`

Owns SQLite schema management and chunk ingestion into the lexical index. It should create:

- `chunks_fts`: FTS5 virtual table for searchable text fields
- `chunk_metadata`: ordinary table for metadata hydration

It should support index rebuild from local chunk JSON files under `data/chunks/`.

#### `lexical_retriever.py`

Owns the core search path. It should:

1. Accept a normalized query object, retrieval constraints, and top-k.
2. Build an FTS5 `MATCH` query from normalized text and protected phrases.
3. Query `chunks_fts`, rank with `bm25()`, and limit to top-k.
4. Hydrate metadata from `chunk_metadata`.
5. Attach lightweight match signals.
6. Return stable lexical candidate objects.

#### `match_signals.py`

Owns simple, inspectable post-query signals only. Initial signals should include:

- `exact_phrase_hits`
- `protected_phrase_hits`
- `section_path_hit`
- `token_overlap_count`

These are debug-oriented ranking clues, not secondary ranking stages.

## 4. Data Model and Contracts

### Normalized Query Contract

Issue #33 should depend on a typed contract shaped like:

```python
@dataclass(frozen=True)
class NormalizedQuery:
    raw_query: str
    normalized_text: str
    tokens: list[str]
    protected_phrases: list[str]
    aliases_applied: list[dict[str, str]]
```

This may be adapted from the existing Issue #31 dict output by a thin constructor/helper, but the lexical retriever should depend on the typed contract rather than raw ad hoc dict access.

### Retrieval Constraints Contract

Issue #32 already exposes `RetrievalConstraints`. Issue #33 should use that contract directly rather than redefining filter rules locally. The lexical stage may translate accepted constraints into SQL predicates, but the source of truth remains the existing constraints object.

### Candidate Output Contract

```python
@dataclass(frozen=True)
class LexicalCandidate:
    chunk_id: str
    document_id: str
    rank: int
    raw_score: float
    score_direction: str
    chunk_type: str
    source_ref: dict[str, object]
    locator: dict[str, object]
    match_signals: dict[str, object]
```

`score_direction` should be fixed to `"lower_is_better"` for SQLite FTS5 BM25 output so downstream consumers do not need to infer score semantics.

## 5. Index Design

### FTS Fields

The lexical baseline only needs the chunk fields already produced by the chunker:

- `chunk_id`
- `document_id`
- `content`
- `section_path_text`
- `chunk_type`
- `source_id`
- `edition`
- `source_layer`

`section_path_text` should be derived from `locator.section_path` and indexed because many rules queries are heading-dominant rather than body-dominant. This preserves the heading/body relationship emphasized in the retrieval design docs.

### Table Separation

The database should use a two-layer structure:

- `chunks_fts` for FTS5 search
- `chunk_metadata` for structured hydration

This keeps full-text concerns separate from chunk metadata, avoids pushing full JSON blobs into the FTS table, and makes post-query hydration straightforward.

## 6. Query and Ranking Behavior

The minimum retrieval algorithm should be:

1. Receive normalized query plus constraints.
2. Extract `normalized_text` and `protected_phrases`.
3. Build an FTS5 `MATCH` expression.
4. Execute lexical retrieval with `bm25()` ordering.
5. Take top-k rows.
6. Compute match signals.
7. Return raw lexical candidates.

Issue #33 must stop there. It must not:

- merge adjacent chunks
- collapse near-duplicates
- group by section
- choose final evidence blocks

Those behaviors belong to Issues #34 and #35.

## 7. Testing Strategy

### Recall Smoke Tests

Use real local SRD chunk data and assert expected chunks appear in top-k for:

- `fighter hit die`
- `attack of opportunity`
- `turn undead`
- `what are bonus feats`

The tests should verify presence in top-k and guard against obvious rank regressions.

### Output Contract Tests

Assert each returned candidate includes:

- `chunk_id`
- `rank`
- `raw_score`
- `score_direction`
- `match_signals`
- `source_ref`
- `locator`

### Match Signal Tests

Assert:

- exact phrase queries populate `exact_phrase_hits`
- protected phrase matches populate `protected_phrase_hits`
- heading matches set `section_path_hit`

## 8. Key Decisions

- Use SQLite FTS5 + BM25 now because it is local, inspectable, and sufficient for lexical-first MVP retrieval.
- Keep lexical retrieval separate from normalization and hard filtering to preserve issue boundaries.
- Index section-path text alongside chunk content because rules retrieval often hinges on section titles.
- Return raw candidates only; postpone consolidation and evidence-pack shaping.

## 9. Alternatives Considered

### Pure Python BM25 over in-memory JSON

Rejected for now because it would add custom ranking/index code where SQLite FTS5 already provides deterministic local search primitives with lower maintenance cost.

### Single-table FTS-only storage

Rejected because stuffing all metadata into the FTS table makes hydration and future debugging noisier. A separate metadata table keeps responsibilities cleaner.

### Pulling filter logic into SQL only

Rejected because Issue #32 already defines the admitted-source boundary. SQL should implement those constraints, not redefine them.

## 10. Risks and Open Questions

- SQLite builds without FTS5 support would block this approach; implementation should fail clearly if FTS5 is unavailable.
- FTS5 query syntax around multiword protected phrases needs careful handling to avoid accidental query broadening.
- Some recall gaps may still come from coarse chunking rather than lexical retrieval itself; tests should distinguish ranking misses from corpus-shape limitations.

## 11. Next Steps

1. Add TDD coverage for lexical candidate retrieval behavior.
2. Implement typed retrieval contracts.
3. Implement index build/hydration helpers over local chunk JSON.
4. Implement lexical retrieval and match signals.
5. Verify deterministic recall and output shape against real SRD chunks.
