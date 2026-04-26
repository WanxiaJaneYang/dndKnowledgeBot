# Issue #91 Debug UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the local Streamlit debug UI for the retrieval/answer pipeline, including the additive composer decision contract needed to inspect slot-filling behavior.

**Architecture:** Build this in two slices. Slice 1 adds the answer-pipeline contract and composer API needed to expose slot decisions without breaking existing callers. Slice 2 adds the Streamlit UI as an additive package under `scripts/ui/`, keeping `streamlit` imports isolated to `debug_app.py` and leaving formatting/state helpers pure-Python and unit-testable.

**Tech Stack:** Python, pytest, Streamlit, existing retrieval and answer pipeline modules under `scripts/`

---

### Task 1: Verify Baseline in an Isolated Worktree

**Files:**
- Modify: none
- Test: `tests/test_answer_composer.py`, `tests/test_answer_pipeline.py`, `tests/test_answer_citation_binder.py`, `tests/test_answer_support_assessor.py`

**Step 1: Verify worktree is clean**

Run: `git status --short --branch`
Expected: clean `issue-91-debug-ui-impl` branch

**Step 2: Verify answer test baseline with repo root on `PYTHONPATH`**

Run: `$env:PYTHONPATH='.'; pytest tests/test_answer_composer.py tests/test_answer_pipeline.py tests/test_answer_citation_binder.py tests/test_answer_support_assessor.py -q`
Expected: passing baseline or only pre-existing failures unrelated to `#91`

### Task 2: Add Failing Tests for the Composer Decision Contract

**Files:**
- Modify: `tests/test_answer_composer.py`
- Test: `tests/test_answer_composer.py`

**Step 1: Write failing tests for additive decision output**

Add tests that assert:
- `compose_segments_with_decisions(pack)` returns `(segments, decisions)`
- the primary slot always emits a filled `SlotDecision`
- slot 1 emits either a filled sibling decision or `no_sibling_available`
- slot 2 emits either a filled cross-section/sibling decision or the correct skip reason
- cross-section rejection reasons are recorded for subset-hit candidates

**Step 2: Run just the new tests to verify RED**

Run: `$env:PYTHONPATH='.'; pytest tests/test_answer_composer.py -q`
Expected: FAIL because `compose_segments_with_decisions` / `SlotDecision` do not exist yet

### Task 3: Implement the Additive Composer Decision API

**Files:**
- Modify: `scripts/answer/contracts.py`
- Modify: `scripts/answer/composer.py`
- Modify: `scripts/answer/__init__.py`
- Test: `tests/test_answer_composer.py`

**Step 1: Add the public `SlotDecision` contract**

Add `SlotDecision` to `scripts/answer/contracts.py` with:
- `slot`
- `chosen_role`
- `outcome`
- `chosen_chunk_id`
- `rejected`
- `reason`

**Step 2: Add `compose_segments_with_decisions(pack)`**

Implement the additive API in `scripts/answer/composer.py` and keep `compose_segments(pack)` as a delegating compatibility wrapper.

**Step 3: Record decision details without changing existing segment behavior**

Implement minimal helpers to:
- record the primary slot decision
- record sibling selection / absence for slot 1
- record cross-section candidate rejections for slot 2
- fall back to a sibling for slot 2 when no distinct cross-section is eligible

**Step 4: Export the new public contract/API**

Update `scripts/answer/__init__.py` to export `SlotDecision` and `compose_segments_with_decisions`.

**Step 5: Run the composer tests to verify GREEN**

Run: `$env:PYTHONPATH='.'; pytest tests/test_answer_composer.py -q`
Expected: PASS

### Task 4: Extend Debug-Pipeline Coverage for the New Contract

**Files:**
- Modify: `tests/test_answer_pipeline.py`
- Modify: `scripts/answer/pipeline.py` only if needed
- Test: `tests/test_answer_pipeline.py`

**Step 1: Write failing tests for any affected debug-path behavior**

If the debug serializer or pipeline helpers need to carry composer decisions for the UI, add tests that pin that shape first.

**Step 2: Run targeted tests to verify RED**

Run: `$env:PYTHONPATH='.'; pytest tests/test_answer_pipeline.py -q`
Expected: FAIL only if new debug behavior is required

**Step 3: Implement the minimal change**

Only add pipeline/debug changes that the UI needs immediately. Do not widen schemas or alter strict JSON output.

**Step 4: Run answer-layer tests**

Run: `$env:PYTHONPATH='.'; pytest tests/test_answer_composer.py tests/test_answer_pipeline.py tests/test_answer_citation_binder.py tests/test_answer_support_assessor.py -q`
Expected: PASS

### Task 5: Add Failing Tests for UI State and Formatting Helpers

**Files:**
- Create: `tests/test_ui_state.py`
- Create: `tests/test_ui_panels.py`
- Test: `tests/test_ui_state.py`, `tests/test_ui_panels.py`

**Step 1: Write state tests**

Add tests for:
- append history entry
- newest-first ordering
- cap at 20 items
- restoring query parameters from history entries

**Step 2: Write panel-formatting tests**

Add tests for pure helpers that format:
- answer display data
- slot decision rows
- candidate rows
- citation rows

**Step 3: Run the new UI-helper tests to verify RED**

Run: `$env:PYTHONPATH='.'; pytest tests/test_ui_state.py tests/test_ui_panels.py -q`
Expected: FAIL because `scripts/ui/` helpers do not exist yet

### Task 6: Implement the UI Helper Modules

**Files:**
- Create: `scripts/ui/__init__.py`
- Create: `scripts/ui/state.py`
- Create: `scripts/ui/panels.py`
- Test: `tests/test_ui_state.py`, `tests/test_ui_panels.py`

**Step 1: Implement `QueryHistoryEntry` and state helpers**

Add pure functions that manage session-history values without importing Streamlit.

**Step 2: Implement panel-formatting helpers**

Add pure helpers that convert pipeline objects into table/json/markdown-friendly data structures for `debug_app.py`.

**Step 3: Run the helper tests to verify GREEN**

Run: `$env:PYTHONPATH='.'; pytest tests/test_ui_state.py tests/test_ui_panels.py -q`
Expected: PASS

### Task 7: Add the Streamlit Entry Point and Launch Docs

**Files:**
- Create: `scripts/ui/debug_app.py`
- Modify: `docs/architecture_overview.md`
- Modify: `docs/zh/architecture_overview.md`
- Modify: dependency file if one exists or create one if needed for Streamlit pinning

**Step 1: Add a failing smoke import check if practical**

Prefer a lightweight test only if it does not require booting a Streamlit runtime. Otherwise keep verification manual.

**Step 2: Implement the Streamlit app**

Add:
- missing-index guard using `data/index/srd_35/lexical.db`
- User / Debug toggle
- `top_k` slider
- disabled `edition` and `source_type` controls
- query input + Run button
- answer display
- debug expanders for each pipeline stage
- query history sidebar

**Step 3: Update architecture docs**

Add a short local debug UI subsection and mirror it in `docs/zh/architecture_overview.md`.

### Task 8: Verify the End-to-End Slice

**Files:**
- Verify only

**Step 1: Run targeted automated tests**

Run: `$env:PYTHONPATH='.'; pytest tests/test_answer_composer.py tests/test_answer_pipeline.py tests/test_answer_citation_binder.py tests/test_answer_support_assessor.py tests/test_ui_state.py tests/test_ui_panels.py -q`
Expected: PASS

**Step 2: Manual launch verification**

Run: `$env:PYTHONPATH='.'; streamlit run scripts/ui/debug_app.py`
Expected:
- missing-index error if `lexical.db` is absent
- normal launch if the index is present
- debug panels render data for a representative query

**Step 3: Manual query verification**

Run representative queries such as:
- `attack of opportunity`
- `turn undead`
- one abstain-expected query

Expected:
- User mode shows only the answer or abstention
- Debug mode shows all pipeline stages, including composer slot decisions
