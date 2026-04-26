# Issue #91 - Streamlit Debug UI for the Retrieval/Answer Pipeline

> **Status:** design
> **Target issues:** #91 (primary) - design only; does not close
> **Author:** 2026-04-26

## 1. Goal

Ship a single-user, local-only Streamlit app that exercises the existing
retrieval -> answer pipeline against an arbitrary query and exposes every
intermediate stage in collapsible panels.

Two display modes:

- **User mode**: answer segments + citations only, or the abstain reason.
- **Debug mode**: every pipeline stage's raw output: query normalization,
  constraints, top-k candidates with all `match_signals`, candidate shaping
  groups, evidence-pack JSON, support assessment, composer slot decisions,
  citation binding, raw `--json-debug` payload.

The app is for accelerating iteration on retrieval, composer, and abstain
work. It is not user-facing in any product sense.

## 2. Scope and non-goals

### In scope

- One Streamlit app at `scripts/ui/debug_app.py` plus a few small helper
  modules under `scripts/ui/`.
- A small additive change to `scripts/answer/composer.py` that exposes
  composer slot decisions without breaking the existing
  `compose_segments(pack)` API.
- A sidebar with: User/Debug toggle, editable `top_k`, edition filter,
  source-type filter, and per-session query history.
- Missing-index guard: clean Streamlit error message + instructions to build
  the index, mirroring the CLI guards.
- Unit tests for the composer-decisions contract addition.
- Smoke tests for the UI module's pure formatting helpers. No Streamlit runtime
  tests in v1.
- A short "Local debug UI" subsection in `docs/architecture_overview.md`
  pointing at the launch command. Mirror in the Chinese doc.

### Non-goals

- Multi-user or hosted deployment.
- Editing support-gate strictness, composer slot rules, or any answer policy
  from the UI.
- Persistence beyond the Streamlit session.
- Multi-query batch evaluation.
- Result-side editing.
- Schema changes to `answer_with_citations.schema.json`.

## 3. Proposed design

### 3.1 Pipeline reuse

The UI does not reimplement pipeline logic. It calls, in order:

```text
normalize_query(raw_query)            -> NormalizedQuery
build_constraints(...)                -> RetrievalConstraints
retrieve_lexical(...)                 -> tuple[LexicalCandidate, ...]
shape_candidates(...)                 -> tuple[CandidateGroup, ...]
build_evidence_pack(...)              -> EvidencePack
assess_support(pack)                  -> AssessmentResult
compose_segments_with_decisions(pack) -> (segments, decisions)
bind_citations(segments, pack)        -> (segments, citations)
build_answer(pack)                    -> AnswerResult
```

Every Debug-mode panel renders one of those return values. The UI is layout,
formatting, and interactivity only.

### 3.2 File layout

```text
scripts/ui/
  __init__.py
  debug_app.py        # Streamlit entry point; all st.* rendering lives here
  panels.py           # Pure formatting helpers: produce markdown/table/json-
                      # friendly data for each panel; no Streamlit imports
  state.py            # QueryHistoryEntry + session-state helpers; no
                      # Streamlit imports
tests/
  test_ui_state.py
  test_ui_panels.py
  test_composer_decisions.py
```

`debug_app.py` is the only file that imports `streamlit`.

`SlotDecision` does **not** live under `scripts/ui/`. It is a pipeline/answer
contract consumed by the UI and by future diagnostics work, so it belongs in
`scripts/answer/contracts.py`.

### 3.3 Layout

**Top of main panel:** query input + Run button.

**Always shown in both modes:**

- Answer panel: segments with inline citation markers plus citations table.
- Or abstain reason + trigger code.

**Shown only in Debug mode:**

- Query normalization
- Constraints
- Top-k candidates
- Candidate shaping groups
- Evidence pack
- Support assessment
- Composer slot decisions
- Citation binding
- Raw `--json-debug` output

Each debug panel is an `st.expander`, collapsed by default.

**Sidebar**

- Mode toggle: User / Debug
- `top_k` slider, 1-25, default 10
- `edition` selectbox
- `source_type` selectbox
- DB path read-only display
- Query history

For v1, `edition` and `source_type` are rendered as **disabled selectboxes**
with a single option each (`3.5e` and `srd`). This keeps the UI shape stable
for later expansion without pretending these are meaningfully editable today.

### 3.4 Composer-decisions contract addition

`scripts/answer/composer.py` currently returns `tuple[_ComposedSegment, ...]`
with no record of which candidates were considered for each slot or why a slot
was filled or left empty. Add a parallel API:

```python
@dataclass(frozen=True)
class SlotDecision:
    """Records why a composer slot was filled or left empty."""

    slot: Literal["primary", "sibling", "cross-section", "fallback-sibling"]
    chosen_role: Literal["primary", "sibling", "cross-section"] | None
    outcome: Literal["filled", "skipped"]
    chosen_chunk_id: str | None
    rejected: tuple[tuple[str, str, str], ...]
    reason: str


def compose_segments_with_decisions(
    pack: EvidencePack,
) -> tuple[tuple[_ComposedSegment, ...], tuple[SlotDecision, ...]]:
    """Like compose_segments(pack) but also returns per-slot decisions."""
```

`compose_segments(pack)` keeps its existing signature and behavior. It calls
`compose_segments_with_decisions(pack)` internally and discards the decisions.

Why `slot` and `chosen_role` are separate:

- `slot` describes the decision site in the composer algorithm.
- `chosen_role` stays in the existing `_ComposedSegment.role` vocabulary:
  `"primary"`, `"sibling"`, `"cross-section"`.
- This avoids polluting the existing segment mental model with a synthetic
  `"fallback-sibling"` role.

**Slot-level outcome reasons**

- `"no_sibling_available"`: slot 1 had no candidate in the primary's
  `(document_id, section_root)` group.
- `"no_distinct_cross_section"`: the cross-section slot had no eligible
  candidate after applying the distinct-signal rule.
- `"no_fallback_sibling_available"`: the fallback-sibling slot was attempted
  and also found no eligible sibling.

These reasons stay single-purpose. The cross-section slot and fallback-sibling
slot do not share a merged failure reason.

**Per-candidate rejection reasons**

- `"hit_set_subset_of_primary"`: a cross-section candidate was considered but
  its `exact_phrase_hits + protected_phrase_hits` signal set was a subset of
  the primary's.
- `"same_group_as_primary"`: a candidate was filtered out of the cross-section
  search because it shares `(document_id, section_root)` with the primary.
- `"already_used_in_earlier_slot"`: applies during fallback-sibling attempts
  where a sibling was already taken by slot 1.

**Primary slot shape**

The primary slot is included for completeness, even though it is trivial in v1.
Its decision always has:

- `slot="primary"`
- `chosen_role="primary"`
- `outcome="filled"`
- `chosen_chunk_id=pack.evidence[0].chunk_id`
- `rejected=()`
- `reason="top_ranked_evidence_item"`

### 3.5 Mode behavior

`User mode`

- Render the Answer panel only.
- Hide the pipeline trace section entirely.

`Debug mode`

- Render Answer panel.
- Render every pipeline trace panel below it, all collapsed.
- Render a "Composer slot decisions" panel from `SlotDecision` rows.

### 3.6 Missing-index guard

Mirror `scripts/answer_question.py`:

- On app start, check `data/index/srd_35/lexical.db`.
- If missing, render one Streamlit error block with the missing path and this
  recovery command:

  `python scripts/chunk_srd_35.py`

- Hide the rest of the UI until the index exists.

### 3.7 Query history

Stored in `st.session_state["query_history"]: list[QueryHistoryEntry]`.

```python
@dataclass(frozen=True)
class QueryHistoryEntry:
    query: str
    top_k: int
    edition: str
    source_type: str
    ran_at: str  # ISO-8601
```

Entries are appended on each Run, capped at 20, newest shown first.

## 4. Data model

### 4.1 New dataclasses

- `scripts/answer/contracts.py`: add `SlotDecision`.
- `scripts/ui/state.py`: add `QueryHistoryEntry`.

There is no `scripts/ui/contracts.py` in this design.

### 4.2 No external schema changes

`answer_with_citations.schema.json` does not change. The only new contract is
the internal answer-pipeline contract for `SlotDecision`.

## 5. Key decisions

1. **Streamlit, not Gradio / FastAPI / a SPA.** Lowest implementation cost for
   a local-only debug tool.
2. **No Streamlit imports outside `debug_app.py`.** `panels.py` and `state.py`
   stay pure-Python. `panels.py` returns formatting-ready data; `debug_app.py`
   owns all `st.*` calls.
3. **Compose-with-decisions is additive.** Existing `compose_segments(pack)`
   remains unchanged for callers.
4. **Read-only on policy.** The UI visualizes current policy; it does not tune
   policy.
5. **Editable inputs are intentionally narrow.** `top_k` is editable. In v1,
   `edition` and `source_type` keep the shape of selectable controls but are
   disabled because only one value exists.
6. **Session-only history.** No persistence in v1.
7. **Missing-index is a full-page error state.**

## 6. Alternatives considered

- **Gradio.** Awkward for a multi-panel pipeline-inspection UI.
- **FastAPI + frontend.** Too much code for a local-only debug tool.
- **Jupyter notebook.** Poor interaction loop for repeated single-query runs.
- **Recompute slot decisions in the UI layer.** Rejected because it risks drift
  from composer behavior.
- **Schema change for slot decisions.** Rejected because slot decisions are an
  internal pipeline concern, not part of the answer contract.

## 7. Risks and open questions

1. **Streamlit version pinning.** Recommendation: `streamlit>=1.30,<2`.
2. **sqlite handle reuse across Streamlit reruns.** Fresh open per Run is fine
   at this scale; optimize later if needed.
3. **No end-to-end UI test in v1.** Acceptable for a personal debug tool.
4. **Rejected-candidate tuple typing.** `(chunk_id, reason_code, detail)` is
   compact but unnamed; revisit later if downstream consumers want stronger
   typing.
5. **`top_k` upper bound.** 25 is generous for a debug UI; revisit if needed.

## 8. Next steps

This PR is docs-only. The implementation PR closes #91.

1. **This PR.** Spec review and approval.
2. **Implementation PR.** Add `SlotDecision` to
   `scripts/answer/contracts.py`; implement the additive composer API; add the
   `scripts/ui/` package (`state.py`, `panels.py`, `debug_app.py`); implement
   the missing-index guard; add the short architecture docs note; pin
   `streamlit>=1.30,<2`.
3. **Manual verification.** Launch the app against the real `lexical.db`; run
   representative success and abstain queries; capture screenshots for PR
   evidence.
