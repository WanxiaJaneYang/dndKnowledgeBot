# Query Normalization Term Assets Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace hardcoded query-normalization term lists with file-backed SRD term assets, extracted primarily from local `srd_35` data and suitable for ongoing review.

**Architecture:** Add a retrieval term-assets module that loads reviewed assets from JSON files and a separate extraction script that scans local canonical/chunk SRD outputs to generate candidate terms. Keep runtime normalization limited to reviewed `protected_phrases` and `canonical_aliases`, while preserving larger candidate/review files outside the hot path.

**Tech Stack:** Python stdlib, existing `scripts/` layout, unittest, local `data/canonical/srd_35` and `data/chunks/srd_35`

---

### Task 1: Add failing tests for file-backed term assets

**Files:**
- Modify: `tests/test_query_normalization.py`
- Create: `tests/test_retrieval_term_assets.py`

**Step 1: Write the failing test**
- Assert normalization no longer depends on hardcoded module constants.
- Assert runtime assets are loaded from dedicated JSON files.
- Assert at least one SRD-derived multiword term beyond the current tiny seed set is available.

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_query_normalization tests.test_retrieval_term_assets -v`
Expected: FAIL because the term-asset loader/files do not exist yet.

**Step 3: Write minimal implementation**
- Add runtime asset files and loader module.
- Update normalization to consume loaded assets.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_query_normalization tests.test_retrieval_term_assets -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_query_normalization.py tests/test_retrieval_term_assets.py scripts/retrieval/term_assets.py configs/retrieval_terms/
git commit -m "Issue #31: load retrieval term assets from files"
```

### Task 2: Add failing tests for SRD candidate extraction

**Files:**
- Create: `tests/test_extract_retrieval_terms.py`
- Create: `scripts/extract_retrieval_terms.py`

**Step 1: Write the failing test**
- Assert candidate extraction reads local SRD canonical/chunk roots.
- Assert it emits deterministic buckets such as `protected_phrase_candidates`.
- Assert obvious SRD terms like `attack of opportunity`, `spell resistance`, and `turn undead` appear in the extracted candidate set.

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_extract_retrieval_terms -v`
Expected: FAIL because the extraction script/module does not exist yet.

**Step 3: Write minimal implementation**
- Build deterministic extraction helpers over local JSON assets.
- Exclude legal/OGL noise and trivial phrases.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_extract_retrieval_terms -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_extract_retrieval_terms.py scripts/extract_retrieval_terms.py
git commit -m "Issue #31: add SRD retrieval term extraction"
```

### Task 3: Materialize reviewed term asset files

**Files:**
- Create: `configs/retrieval_terms/protected_phrases.json`
- Create: `configs/retrieval_terms/canonical_aliases.json`
- Create: `configs/retrieval_terms/surface_variants.json`
- Create: `configs/retrieval_terms/extraction_candidates.json`

**Step 1: Write/update failing test**
- Assert runtime file shape and minimum reviewed coverage.
- Assert candidate file is larger than runtime-protected phrases.

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_retrieval_term_assets -v`
Expected: FAIL until reviewed/candidate files are created with the expected shape.

**Step 3: Write minimal implementation**
- Populate reviewed runtime assets from SRD-derived high-value terms.
- Populate candidate file from extraction output for future review.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_retrieval_term_assets -v`
Expected: PASS

**Step 5: Commit**

```bash
git add configs/retrieval_terms/ tests/test_retrieval_term_assets.py
git commit -m "Issue #31: add reviewed SRD retrieval term assets"
```

### Task 4: Verify integrated normalization behavior and update PR evidence

**Files:**
- Modify: `scripts/retrieval/query_normalization.py`
- Update PR description with larger inspectable examples and asset summary

**Step 1: Write/update failing test**
- Assert normalization protects newly reviewed multiword phrases from file assets.
- Assert alias expansion still works with file-backed terms.

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_query_normalization -v`
Expected: FAIL until integration is complete.

**Step 3: Write minimal implementation**
- Finish integration and cleanup.

**Step 4: Run full verification**

Run: `python -m unittest tests.test_query_normalization tests.test_retrieval_term_assets tests.test_extract_retrieval_terms tests.test_chunker -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/retrieval/query_normalization.py tests/ docs/plans/
git commit -m "Issue #31: expand query normalization with SRD term assets"
```
