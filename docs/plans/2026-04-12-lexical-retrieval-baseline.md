# Lexical Retrieval Baseline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build Issue #33 as a lexical-first candidate generator using SQLite FTS5 and BM25 over Phase 1 chunk data, returning stable ranked candidates with lightweight match signals.

**Architecture:** Keep retrieval layered: Issue #31 normalizes the query, Issue #32 defines hard boundaries, and Issue #33 performs lexical indexing, lexical search, and signal attachment only. Use a two-table SQLite layout with `chunks_fts` for search and `chunk_metadata` for hydration so the output contract stays stable and inspectable.

**Tech Stack:** Python stdlib (`sqlite3`, `json`, `dataclasses`, `pathlib`), existing `scripts/retrieval/` package, pytest, local `data/chunks/srd_35`

---

### Task 1: Add failing contract tests for lexical retrieval outputs

**Files:**
- Create: `tests/test_lexical_retrieval.py`
- Modify: `scripts/retrieval/__init__.py`

**Step 1: Write the failing test**
- Add a test that imports the planned retrieval contracts and retriever surface from `scripts.retrieval`.
- Assert the public API can represent a lexical candidate with `chunk_id`, `rank`, `raw_score`, `score_direction`, `source_ref`, `locator`, and `match_signals`.
- Add a test that expects `score_direction == "lower_is_better"`.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_lexical_retrieval.py -v`
Expected: FAIL because the lexical retrieval contracts and exports do not exist yet.

**Step 3: Write minimal implementation**
- Create `scripts/retrieval/contracts.py`.
- Add dataclasses for `NormalizedQuery` adapter input and `LexicalCandidate`.
- Export the new contracts from `scripts/retrieval/__init__.py`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_lexical_retrieval.py -v`
Expected: PASS for the contract-shape tests.

**Step 5: Commit**

```bash
git add tests/test_lexical_retrieval.py scripts/retrieval/contracts.py scripts/retrieval/__init__.py
git commit -m "feat(retrieval): add lexical retrieval contracts"
```

### Task 2: Add failing tests for SQLite lexical index build and metadata hydration

**Files:**
- Modify: `tests/test_lexical_retrieval.py`
- Create: `scripts/retrieval/lexical_index.py`

**Step 1: Write the failing test**
- Add a test that builds a temporary SQLite database from a small fixture chunk set or a sampled local SRD chunk subset.
- Assert the builder creates `chunks_fts` and `chunk_metadata`.
- Assert `section_path_text` is derived from `locator.section_path`.
- Assert metadata rows preserve `chunk_type`, `source_ref`, and `locator` for later hydration.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_lexical_retrieval.py -k "index or hydration" -v`
Expected: FAIL because `lexical_index.py` and index build logic do not exist yet.

**Step 3: Write minimal implementation**
- Create the SQLite schema creation helpers.
- Add chunk ingestion helpers that read chunk JSON, derive `section_path_text`, and insert rows into both tables.
- Add clear failure when SQLite FTS5 support is unavailable.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_lexical_retrieval.py -k "index or hydration" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_lexical_retrieval.py scripts/retrieval/lexical_index.py
git commit -m "feat(retrieval): add sqlite lexical index builder"
```

### Task 3: Add failing tests for match signal computation

**Files:**
- Modify: `tests/test_lexical_retrieval.py`
- Create: `scripts/retrieval/match_signals.py`

**Step 1: Write the failing test**
- Add a test that a query for `attack of opportunity` records non-empty `exact_phrase_hits` and `protected_phrase_hits` when the phrase appears exactly.
- Add a test that a matching heading in `section_path_text` sets `section_path_hit` to `True`.
- Add a test that token overlap counts are deterministic for a simple candidate row.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_lexical_retrieval.py -k signals -v`
Expected: FAIL because `match_signals.py` does not exist yet.

**Step 3: Write minimal implementation**
- Implement pure helper functions that compute `exact_phrase_hits`, `protected_phrase_hits`, `section_path_hit`, and `token_overlap_count`.
- Keep this module read-only and post-query; do not add reranking here.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_lexical_retrieval.py -k signals -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_lexical_retrieval.py scripts/retrieval/match_signals.py
git commit -m "feat(retrieval): add lexical match signals"
```

### Task 4: Add failing tests for lexical search over normalized queries and constraints

**Files:**
- Modify: `tests/test_lexical_retrieval.py`
- Create: `scripts/retrieval/lexical_retriever.py`

**Step 1: Write the failing test**
- Add tests that call the lexical retriever with a normalized query object plus existing `RetrievalConstraints`.
- Assert top-k results return ranked `LexicalCandidate` objects.
- Assert rejected source boundaries are not returned when constraints exclude them.
- Assert search results remain raw candidates and are not merged or deduplicated.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_lexical_retrieval.py -k "retriever or constraints" -v`
Expected: FAIL because the lexical retriever surface does not exist yet.

**Step 3: Write minimal implementation**
- Implement `LexicalRetriever.search()`.
- Translate normalized text and protected phrases into an FTS5 `MATCH` expression.
- Join or hydrate metadata rows, compute `bm25()` scores, assign rank values, and attach match signals.
- Reuse Issue #32 constraints instead of redefining filters locally.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_lexical_retrieval.py -k "retriever or constraints" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_lexical_retrieval.py scripts/retrieval/lexical_retriever.py
git commit -m "feat(retrieval): add lexical candidate retrieval"
```

### Task 5: Add failing recall smoke tests against real SRD chunk data

**Files:**
- Modify: `tests/test_lexical_retrieval.py`
- Review: `data/chunks/srd_35/`

**Step 1: Write the failing test**
- Add deterministic recall smoke tests for:
  - `fighter hit die`
  - `attack of opportunity`
  - `turn undead`
  - `what are bonus feats`
- Assert an expected chunk or section identifier appears in top-k.
- Add a mild rank guard where practical so obvious regressions are caught.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_lexical_retrieval.py -k "recall or smoke" -v`
Expected: FAIL until the lexical retriever and index are wired to real chunk data correctly.

**Step 3: Write minimal implementation**
- Adjust FTS field coverage or match expression construction only as needed to satisfy the tests.
- Keep the retriever lexical-first and domain-aware; do not add semantic fallback.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_lexical_retrieval.py -k "recall or smoke" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_lexical_retrieval.py scripts/retrieval/
git commit -m "feat(retrieval): cover lexical recall smoke tests"
```

### Task 6: Run integrated verification and document the boundary

**Files:**
- Modify: `docs/plans/2026-04-12-lexical-retrieval-baseline-design.md` if implementation clarifies wording
- Review: `scripts/retrieval/`
- Review: `tests/test_lexical_retrieval.py`

**Step 1: Write/update any missing failing test**
- Add one final boundary test asserting the Issue #33 output contains raw ranked candidates only and does not expose consolidation fields from future issues.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_lexical_retrieval.py -k boundary -v`
Expected: FAIL if the output contract has drifted beyond Issue #33 scope.

**Step 3: Write minimal implementation**
- Tighten exports, docs, or contract fields as needed.

**Step 4: Run full verification**

Run: `pytest tests/test_lexical_retrieval.py tests/test_query_normalization.py tests/test_retrieval_filters.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add docs/plans/2026-04-12-lexical-retrieval-baseline-design.md docs/plans/2026-04-12-lexical-retrieval-baseline.md tests/test_lexical_retrieval.py scripts/retrieval/
git commit -m "feat(retrieval): implement lexical-first candidate baseline"
```
