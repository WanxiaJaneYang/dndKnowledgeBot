# Lexical Retriever End-to-End Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire existing lexical retrieval primitives into a `retrieve_lexical()` function that goes from normalized query to ranked `LexicalCandidate` objects with populated match signals.

**Architecture:** A new `scripts/retrieval/lexical_retriever.py` module composes FTS expression building, over-fetch search, match signal hydration, hard filtering, and result truncation. A package-private `_search_raw()` helper in `lexical_index.py` exposes row data (including content and section_path_text) needed for signal hydration without changing the existing public API.

**Tech Stack:** Python 3.13, SQLite FTS5, pytest, existing `scripts/retrieval/` modules

**Spec:** `docs/plans/2026-04-20-lexical-retriever-end-to-end.md`

---

### Task 1: Add `_search_raw()` to `lexical_index.py`

**Files:**
- Modify: `scripts/retrieval/lexical_index.py`
- Test: `tests/test_lexical_retriever.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_lexical_retriever.py` with a test for the raw search helper:

```python
"""Tests for Issue #43 lexical retriever end-to-end path."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.retrieval import NormalizedQuery
from scripts.retrieval.lexical_index import _search_raw, build_chunk_index


@pytest.fixture
def sample_chunk() -> dict:
    return {
        "chunk_id": "chunk::srd_35::combat::001_attack_of_opportunity",
        "document_id": "srd_35::combat::001_attack_of_opportunity",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["Combat", "Attack of Opportunity"],
            "source_location": "Combat.rtf#001_attack_of_opportunity",
        },
        "chunk_type": "rule_section",
        "content": "An attack of opportunity is a single melee attack.",
    }


def _write_chunk(path: Path, chunk: dict) -> Path:
    path.write_text(json.dumps(chunk), encoding="utf-8")
    return path


def test_search_raw_returns_row_data_with_content(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "aoo.json", sample_chunk)
    build_chunk_index(db_path, [chunk_path])

    rows = _search_raw(db_path, '"attack of opportunity"', top_k=3)

    assert len(rows) == 1
    row = rows[0]
    assert row["chunk_id"] == sample_chunk["chunk_id"]
    assert row["content"] == sample_chunk["content"]
    assert row["section_path_text"] == "Combat Attack of Opportunity"
    assert row["source_ref"] == sample_chunk["source_ref"]
    assert row["locator"] == sample_chunk["locator"]
    assert row["raw_score"] <= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_lexical_retriever.py::test_search_raw_returns_row_data_with_content -v`
Expected: FAIL — `ImportError: cannot import name '_search_raw'`

- [ ] **Step 3: Write `_search_raw()` implementation**

Add to `scripts/retrieval/lexical_index.py` after `search_chunk_index`:

```python
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
                bm25(chunks_fts) AS raw_score
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
        }
        for row in rows
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_lexical_retriever.py::test_search_raw_returns_row_data_with_content -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/retrieval/lexical_index.py tests/test_lexical_retriever.py
git commit -m "feat(retrieval): add _search_raw for signal hydration"
```

---

### Task 2: Implement `_build_fts_expression()`

**Files:**
- Create: `scripts/retrieval/lexical_retriever.py`
- Test: `tests/test_lexical_retriever.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lexical_retriever.py`:

```python
from scripts.retrieval.lexical_retriever import _build_fts_expression


def test_fts_expression_single_bare_token():
    query = NormalizedQuery(
        raw_query="fighter",
        normalized_text="fighter",
        tokens=["fighter"],
        protected_phrases=[],
        aliases_applied=[],
    )
    assert _build_fts_expression(query) == "fighter"


def test_fts_expression_protected_phrase_quoted():
    query = NormalizedQuery(
        raw_query="hit points",
        normalized_text="hit points",
        tokens=["hit points"],
        protected_phrases=["hit points"],
        aliases_applied=[],
    )
    assert _build_fts_expression(query) == '"hit points"'


def test_fts_expression_mixed_tokens_and_protected_phrases():
    query = NormalizedQuery(
        raw_query="fighter hp",
        normalized_text="fighter hit points",
        tokens=["fighter", "hit points"],
        protected_phrases=["hit points"],
        aliases_applied=[{"source": "hp", "target": "hit points"}],
    )
    result = _build_fts_expression(query)
    assert result == '"fighter hit points" OR fighter OR "hit points"'


def test_fts_expression_multiple_bare_tokens():
    query = NormalizedQuery(
        raw_query="melee damage",
        normalized_text="melee damage",
        tokens=["melee", "damage"],
        protected_phrases=[],
        aliases_applied=[],
    )
    result = _build_fts_expression(query)
    assert result == '"melee damage" OR melee OR damage'


def test_fts_expression_empty_tokens_returns_empty_string():
    query = NormalizedQuery(
        raw_query="",
        normalized_text="",
        tokens=[],
        protected_phrases=[],
        aliases_applied=[],
    )
    assert _build_fts_expression(query) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_lexical_retriever.py -k "fts_expression" -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.retrieval.lexical_retriever'`

- [ ] **Step 3: Write `_build_fts_expression()` implementation**

Create `scripts/retrieval/lexical_retriever.py`:

```python
"""End-to-end lexical retriever for Phase 1."""
from __future__ import annotations

from .contracts import NormalizedQuery


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_lexical_retriever.py -k "fts_expression" -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/retrieval/lexical_retriever.py tests/test_lexical_retriever.py
git commit -m "feat(retrieval): add FTS expression builder"
```

---

### Task 3: Implement `retrieve_lexical()`

**Files:**
- Modify: `scripts/retrieval/lexical_retriever.py`
- Test: `tests/test_lexical_retriever.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lexical_retriever.py`:

```python
from scripts.retrieval import LexicalCandidate, build_constraints
from scripts.retrieval.lexical_retriever import retrieve_lexical


def test_retrieve_lexical_returns_candidates_with_populated_signals(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "aoo.json", sample_chunk)
    build_chunk_index(db_path, [chunk_path])

    query = NormalizedQuery(
        raw_query="attack of opportunity",
        normalized_text="attack of opportunity",
        tokens=["attack of opportunity"],
        protected_phrases=["attack of opportunity"],
        aliases_applied=[],
    )
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert len(results) == 1
    candidate = results[0]
    assert isinstance(candidate, LexicalCandidate)
    assert candidate.chunk_id == sample_chunk["chunk_id"]
    assert candidate.rank == 1
    assert candidate.match_signals["exact_phrase_hits"] == ["attack of opportunity"]
    assert candidate.match_signals["protected_phrase_hits"] == ["attack of opportunity"]
    assert candidate.match_signals["section_path_hit"] is True
    assert candidate.match_signals["token_overlap_count"] >= 3


def test_retrieve_lexical_filters_out_non_matching_editions(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunk_5e = {
        **sample_chunk,
        "chunk_id": "chunk::phb_5e::combat::001",
        "source_ref": {
            **sample_chunk["source_ref"],
            "source_id": "phb_5e",
            "edition": "5e",
            "source_type": "core_rulebook",
            "authority_level": "official",
        },
    }
    path_35 = _write_chunk(tmp_path / "aoo_35.json", sample_chunk)
    path_5e = _write_chunk(tmp_path / "aoo_5e.json", chunk_5e)
    build_chunk_index(db_path, [path_35, path_5e])

    query = NormalizedQuery(
        raw_query="attack of opportunity",
        normalized_text="attack of opportunity",
        tokens=["attack of opportunity"],
        protected_phrases=["attack of opportunity"],
        aliases_applied=[],
    )
    constraints = build_constraints()
    results = retrieve_lexical(query, constraints=constraints, db_path=db_path, top_k=5)

    assert all(r.source_ref["edition"] == "3.5e" for r in results)
    assert len(results) == 1


def test_retrieve_lexical_returns_empty_for_no_match(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "aoo.json", sample_chunk)
    build_chunk_index(db_path, [chunk_path])

    query = NormalizedQuery(
        raw_query="psionics",
        normalized_text="psionics",
        tokens=["psionics"],
        protected_phrases=[],
        aliases_applied=[],
    )
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert results == []


def test_retrieve_lexical_empty_tokens_returns_empty(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunk_path = _write_chunk(tmp_path / "aoo.json", sample_chunk)
    build_chunk_index(db_path, [chunk_path])

    query = NormalizedQuery(
        raw_query="",
        normalized_text="",
        tokens=[],
        protected_phrases=[],
        aliases_applied=[],
    )
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert results == []


def test_retrieve_lexical_respects_top_k(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunks = []
    for i in range(5):
        chunk = {
            **sample_chunk,
            "chunk_id": f"chunk::srd_35::combat::{i:03d}_attack",
            "document_id": f"srd_35::combat::{i:03d}_attack",
            "content": f"An attack of opportunity is a melee attack variant {i}.",
        }
        chunks.append(_write_chunk(tmp_path / f"chunk_{i}.json", chunk))
    build_chunk_index(db_path, chunks)

    query = NormalizedQuery(
        raw_query="attack of opportunity",
        normalized_text="attack of opportunity",
        tokens=["attack of opportunity"],
        protected_phrases=["attack of opportunity"],
        aliases_applied=[],
    )
    results = retrieve_lexical(query, db_path=db_path, top_k=3)

    assert len(results) == 3
    assert [r.rank for r in results] == [1, 2, 3]


def test_retrieve_lexical_reranks_after_filtering(tmp_path, sample_chunk):
    db_path = tmp_path / "retrieval.db"
    chunk_35 = sample_chunk
    chunk_5e = {
        **sample_chunk,
        "chunk_id": "chunk::phb_5e::combat::001",
        "document_id": "phb_5e::combat::001",
        "source_ref": {
            **sample_chunk["source_ref"],
            "source_id": "phb_5e",
            "edition": "5e",
            "source_type": "core_rulebook",
            "authority_level": "official",
        },
    }
    path_35 = _write_chunk(tmp_path / "aoo_35.json", chunk_35)
    path_5e = _write_chunk(tmp_path / "aoo_5e.json", chunk_5e)
    build_chunk_index(db_path, [path_35, path_5e])

    query = NormalizedQuery(
        raw_query="attack of opportunity",
        normalized_text="attack of opportunity",
        tokens=["attack of opportunity"],
        protected_phrases=["attack of opportunity"],
        aliases_applied=[],
    )
    constraints = build_constraints()
    results = retrieve_lexical(query, constraints=constraints, db_path=db_path, top_k=5)

    assert len(results) == 1
    assert results[0].rank == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_lexical_retriever.py -k "retrieve_lexical" -v`
Expected: FAIL — `ImportError: cannot import name 'retrieve_lexical'`

- [ ] **Step 3: Write `retrieve_lexical()` implementation**

Add to `scripts/retrieval/lexical_retriever.py`:

```python
from pathlib import Path

from .contracts import LexicalCandidate, NormalizedQuery
from .filters import RetrievalConstraints, build_constraints
from .lexical_index import _search_raw
from .match_signals import build_match_signals

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "index" / "srd_35" / "lexical.db"


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_lexical_retriever.py -k "retrieve_lexical" -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Run the full test file**

Run: `PYTHONPATH=. pytest tests/test_lexical_retriever.py -v`
Expected: PASS (all 12 tests — 1 from Task 1 + 5 from Task 2 + 6 from Task 3)

- [ ] **Step 6: Commit**

```bash
git add scripts/retrieval/lexical_retriever.py tests/test_lexical_retriever.py
git commit -m "feat(retrieval): implement retrieve_lexical end-to-end path"
```

---

### Task 4: Export `retrieve_lexical` and add real-corpus recall tests

**Files:**
- Modify: `scripts/retrieval/__init__.py`
- Modify: `tests/test_lexical_retriever.py`

- [ ] **Step 1: Update `__init__.py` exports**

Add the import and export for `retrieve_lexical` in `scripts/retrieval/__init__.py`:

```python
from .contracts import LexicalCandidate, NormalizedQuery
from .filters import (
    apply_filters,
    build_constraints,
    FilterResult,
    RetrievalConstraints,
)
from .lexical_retriever import retrieve_lexical
from .query_normalization import normalize_query
from .term_assets import get_default_term_assets, load_term_assets

__all__ = [
    "apply_filters",
    "build_constraints",
    "FilterResult",
    "get_default_term_assets",
    "LexicalCandidate",
    "load_term_assets",
    "normalize_query",
    "NormalizedQuery",
    "retrieve_lexical",
    "RetrievalConstraints",
]
```

- [ ] **Step 2: Write real-corpus recall tests**

Append to `tests/test_lexical_retriever.py`:

```python
from scripts.retrieval import normalize_query, retrieve_lexical as retrieve_lexical_public


def _build_index_with_real_chunks(db_path: Path, chunk_filenames: list[str]) -> None:
    chunk_dir = Path("data/chunks/srd_35")
    chunk_paths = [chunk_dir / name for name in chunk_filenames]
    build_chunk_index(db_path, chunk_paths)


def test_real_corpus_recall_turn_undead(tmp_path):
    db_path = tmp_path / "retrieval.db"
    _build_index_with_real_chunks(db_path, ["combatii__029_turning_checks.json"])

    payload = normalize_query("turn undead")
    query = NormalizedQuery.from_query_normalization(payload)
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert results
    assert results[0].chunk_id == "chunk::srd_35::combatii::029_turning_checks"
    assert results[0].match_signals["token_overlap_count"] >= 2


def test_real_corpus_recall_attack_of_opportunity(tmp_path):
    db_path = tmp_path / "retrieval.db"
    _build_index_with_real_chunks(db_path, [
        "combati__001_combati.json",
        "combati__002_how_combat_works.json",
        "combati__006_attacks_of_opportunity.json",
    ])

    payload = normalize_query("attack of opportunity")
    query = NormalizedQuery.from_query_normalization(payload)
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert results
    chunk_ids = [r.chunk_id for r in results]
    assert "chunk::srd_35::combati::006_attacks_of_opportunity" in chunk_ids


def test_real_corpus_recall_fighter_bonus_feats(tmp_path):
    db_path = tmp_path / "retrieval.db"
    _build_index_with_real_chunks(db_path, ["feats__004_fighter_bonus_feats.json"])

    payload = normalize_query("fighter bonus feats")
    query = NormalizedQuery.from_query_normalization(payload)
    results = retrieve_lexical(query, db_path=db_path, top_k=5)

    assert results
    assert results[0].chunk_id == "chunk::srd_35::feats::004_fighter_bonus_feats"
    assert results[0].match_signals["token_overlap_count"] >= 2
```

- [ ] **Step 3: Run all tests**

Run: `PYTHONPATH=. pytest tests/test_lexical_retriever.py -v`
Expected: PASS (all 15 tests)

- [ ] **Step 4: Run the full existing test suite to check for regressions**

Run: `PYTHONPATH=. pytest tests/test_lexical_retrieval.py tests/test_retrieval_filters.py tests/test_query_normalization.py tests/test_retrieval_term_assets.py -v`
Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/retrieval/__init__.py tests/test_lexical_retriever.py
git commit -m "feat(retrieval): export retrieve_lexical, add real-corpus recall tests"
```

---

### Task 5: Push branch and open PR

**Files:** None (git operations only)

- [ ] **Step 1: Run full test suite one final time**

Run: `PYTHONPATH=. pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Push and open PR**

```bash
git push -u origin issue-43-lexical-retriever
gh pr create --title "feat(retrieval): implement lexical retriever end-to-end path" --body "$(cat <<'EOF'
## Summary
Implements the end-to-end lexical retrieval path for #43 (child of #33):
- `retrieve_lexical()` wires query normalization → FTS search → match signal hydration → hard filtering → ranked output
- FTS expression builder converts `NormalizedQuery` into BM25-optimized MATCH expressions
- `_search_raw()` helper exposes row data for signal hydration without changing existing public API
- Real-corpus recall tests for `turn undead`, `attack of opportunity`, `fighter bonus feats`

## Evidence
- All new and existing tests pass
- Candidates return with populated (non-placeholder) match signals
- Hard filters correctly exclude non-matching editions
- Over-fetch + post-filter ensures top_k results survive filtering

## Test plan
- [ ] `pytest tests/test_lexical_retriever.py -v` passes
- [ ] `pytest tests/ -v` passes (no regressions)

Refs #43
EOF
)"
```
