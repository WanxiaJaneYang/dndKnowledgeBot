# Issue #91 — Streamlit Debug UI for the Retrieval/Answer Pipeline

> **Status:** design
> **Target issues:** #91 (primary) — design only; does not close
> **Author:** 2026-04-26

## 1. Goal

Ship a single-user, local-only Streamlit web app that exercises the
existing retrieval → answer pipeline against an arbitrary query and
exposes every intermediate stage in collapsible panels. Two display modes:

- **User mode** — answer segments + citations only, or the abstain reason.
- **Debug mode** — every pipeline stage's raw output: query normalization,
  constraints, top-k candidates with all `match_signals`, candidate shaping
  groups, evidence-pack JSON, support assessment, **composer slot
  decisions** (currently invisible from any output), citation binding,
  raw `--json-debug` payload.

The app is for accelerating iteration on retrieval / composer / abstain
work. It is not user-facing in any product sense; it is a debugging
console for the project's sole user.

## 2. Scope and non-goals

### In scope

- One Streamlit app at `scripts/ui/debug_app.py` plus a few small helper
  modules under `scripts/ui/`.
- A small additive change to `scripts/answer/composer.py` that exposes
  composer slot decisions (which slot was filled by which evidence item
  and why; which candidates were rejected and why) without breaking the
  existing `compose_segments(pack)` API.
- A sidebar with: User/Debug toggle, editable `top_k`, edition filter,
  source-type filter, and a per-session query history (re-run with one
  click).
- Missing-index guard: clean Streamlit error message + instructions to
  build the index, mirroring the CLI guards.
- Unit tests for the composer-decisions contract addition. Smoke test
  for the UI module's pure-data helpers (no Streamlit-runtime tests
  in v1; see Risks §7).
- A short "Local debug UI" subsection in `docs/architecture_overview.md`
  pointing at the launch command. Mirror in the Chinese doc.

### Non-goals

- Multi-user / hosted deployment. Local-only, single user. No auth.
- Editing the support-gate strictness, composer slot rules, or any
  policy from the UI. The UI is read-only on policy; #82 owns
  policy-tuning visibility.
- Persistence beyond the Streamlit session. Query history vanishes on
  app restart. No on-disk session store.
- Multi-query batch evaluation. The gold-set eval has its own CLI
  (`scripts/run_phase1_eval.py`); the debug UI is for ad-hoc
  single-query exploration.
- Result-side editing (e.g. "edit this excerpt and re-render"). Inputs
  in, outputs out; no inline mutation.
- Schema changes to `answer_with_citations.schema.json`. The composer-
  decisions data lives in the `--json-debug` payload structure if it
  shows up there at all; the schema is untouched.

## 3. Proposed design

### 3.1 Pipeline reuse

The UI does not reimplement any pipeline logic. It calls, in order:

```
normalize_query(raw_query)        → NormalizedQuery       (existing)
build_constraints(...)            → RetrievalConstraints  (existing)
retrieve_lexical(...)             → tuple[LexicalCandidate, ...]
shape_candidates(...)             → tuple[CandidateGroup, ...]
build_evidence_pack(...)          → EvidencePack          (existing)
assess_support(pack)              → AssessmentResult      (existing)
compose_segments_with_decisions(pack)
                                  → (segments, decisions) (NEW, §3.4)
bind_citations(segments, pack)    → (segments, citations) (existing)
build_answer(pack)                → AnswerResult          (existing)
```

Every panel in the Debug-mode view renders one of those return values.
The UI's job is layout, formatting, and interactivity — not computation.

### 3.2 File layout

```
scripts/ui/
  __init__.py
  debug_app.py        # Streamlit entry point; layout + panels
  panels.py           # Pure functions: render_normalization_panel(query),
                      #   render_candidates_panel(...), etc. Each takes the
                      #   stage's data and returns nothing (writes to st).
  contracts.py        # NEW dataclass: SlotDecision (see §3.4)
  state.py            # QueryHistoryEntry, session-state helpers (pure;
                      #   no Streamlit imports — Streamlit is the caller).
tests/
  test_ui_state.py        # session-state helpers (pure)
  test_ui_panels.py       # pure formatting helpers (no Streamlit runtime)
  test_composer_decisions.py  # the new compose_with_decisions API
```

`debug_app.py` is the only file that imports `streamlit`. Keeping
Streamlit out of `panels.py`, `state.py`, and `contracts.py` means most
of the UI logic is unit-testable without spinning up the Streamlit
runtime.

### 3.3 Layout

**Top of main panel:** query input + Run button.

```
┌── Main panel ──────────────────────────────────┐
│  Query: [_______________________]   [Run]      │
│                                                 │
│  ━ Answer ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│   (always shown, both modes)                    │
│   - segments with inline [cit_1] markers        │
│   - citations table                             │
│   - or abstain reason + trigger code            │
│                                                 │
│  ━ Pipeline trace ━━━━━━━━━━━━ (Debug mode)    │
│   ▸ Query normalization                         │
│   ▸ Constraints                                 │
│   ▸ Top-k candidates                            │
│   ▸ Candidate shaping groups                    │
│   ▸ Evidence pack (JSON viewer)                 │
│   ▸ Support assessment                          │
│   ▸ Composer slot decisions                     │
│   ▸ Citation binding                            │
│   ▸ Raw --json-debug output                     │
└────────────────────────────────────────────────┘
```

Each `▸` is a `st.expander`, collapsed by default. Reviewers expand only
the panels they care about for the case at hand.

**Sidebar:**

```
┌── Sidebar ──────────────────┐
│  Mode: ( ) User  (•) Debug   │
│                              │
│  top_k: [10  ▼]              │
│  edition: [3.5e ▼]           │
│  source_type: [srd ▼]        │
│  (db path read-only display) │
│                              │
│  ─ History ─                 │
│   • attack of...    [↻]      │
│   • turn undead     [↻]      │
│   • dazzled         [↻]      │
│   ...                        │
└──────────────────────────────┘
```

Editable parameters: `top_k` (slider 1–25, default 10), `edition`
(default `3.5e`, single value for v1), `source_type` (default `srd`,
single value for v1). Anything more (excluded source ids, authority
levels) is read-only display in v1.

History is a list of past queries in the current session. Each entry
shows the query text and a small re-run icon that re-populates the
query input and triggers a Run.

### 3.4 Composer-decisions contract addition

`scripts/answer/composer.py` currently returns
`tuple[_ComposedSegment, ...]` with no record of which candidates were
considered for each slot or why a slot was filled / left empty. Add a
parallel API that exposes this:

```python
@dataclass(frozen=True)
class SlotDecision:
    """Records why a composer slot was filled or left empty.

    role:           Which slot the decision is about.
    outcome:        "filled" — a candidate was accepted into this slot.
                    "skipped" — no eligible candidate; slot stays empty.
    chosen_chunk_id:    chunk_id of the accepted item; None if skipped.
    rejected:       Candidates that were considered but rejected for this
                    slot. Each entry: (chunk_id, reason_code, detail).
    reason:         Short human-readable explanation of the outcome.
    """
    role: Literal["primary", "sibling", "cross-section", "fallback-sibling"]
    outcome: Literal["filled", "skipped"]
    chosen_chunk_id: str | None
    rejected: tuple[tuple[str, str, str], ...]
    reason: str
```

New public function:

```python
def compose_segments_with_decisions(
    pack: EvidencePack,
) -> tuple[tuple[_ComposedSegment, ...], tuple[SlotDecision, ...]]:
    """Like compose_segments(pack) but also returns per-slot decisions."""
```

`compose_segments(pack)` continues to exist with the same signature and
behavior. It calls `compose_segments_with_decisions` internally and
discards the decisions tuple. No existing caller breaks.

Reason codes split into two disjoint sets — one set for slot-level
outcomes (used in `SlotDecision.reason` when `outcome == "skipped"`),
the other for per-candidate rejections (used as the second element of
each tuple in `SlotDecision.rejected`).

**Slot-level outcome reasons** (skipped slots only):

- `"no_sibling_available"` — slot 1 had no candidate in the primary's
  `(document_id, section_root)` group.
- `"no_distinct_cross_section"` — every cross-section candidate's hit
  set was a subset of the primary's; slot 2 cross-section attempt
  exhausted, AND no fallback sibling was available either.
- `"no_fallback_sibling_available"` — set on the synthetic
  `"fallback-sibling"` slot only when slot 2 fell back to a sibling
  search and that search also returned nothing.

**Per-candidate rejection reasons** (entries in `rejected`):

- `"hit_set_subset_of_primary"` — a cross-section candidate was
  considered but its `exact_phrase_hits ∪ protected_phrase_hits` was
  a subset of the primary's. Detail string includes the two sets for
  inspection.
- `"same_group_as_primary"` — a candidate was filtered out of the
  cross-section search because it shares
  `(document_id, section_root)` with the primary.
- `"already_used_in_earlier_slot"` — applies during fallback-sibling
  attempts where a sibling was already taken by slot 1; detail string
  carries the slot identity that consumed the candidate.

**Primary slot shape.** The primary is included in the decisions
tuple for completeness, even though it never has rejections in the
v1 composer (it is always `pack.evidence[0]`). Its `SlotDecision`
always has `outcome="filled"`, `chosen_chunk_id=pack.evidence[0].chunk_id`,
`rejected=()`, and `reason="top-ranked evidence item"`. Consumers
that only care about non-trivial decisions can filter on
`role != "primary"`.

The `SlotDecision.rejected` tuple is `(chunk_id, reason_code,
detail_string)`. `detail_string` is human-readable and may include
short context (e.g., the rejected candidate's hit set vs the primary's).

### 3.5 Mode behavior

`User mode`:

- Render the Answer panel only.
- Hide the Pipeline trace section entirely.
- The sidebar still shows the parameter sliders so the user can change
  `top_k` etc. and re-run.

`Debug mode`:

- Render Answer panel.
- Render every Pipeline trace panel below it, all collapsed.
- The "Composer slot decisions" panel uses the `SlotDecision` data from
  `compose_segments_with_decisions` to render a small table per slot:
  outcome, chosen chunk_id, rejected candidates with reasons.

The toggle is a `st.radio` in the sidebar. State persists across Runs in
the same session.

### 3.6 Missing-index guard

Mirrors `scripts/answer_question.py`:

- On app start, check `data/index/srd_35/lexical.db`.
- If missing, render a single Streamlit error block with the path and the
  build command (the issue #83 follow-up will eventually provide a real
  build CLI; until then the error tells the user to use the
  `python -c "..."` one-liner from CLAUDE.md / the README).
- All other panels are hidden until the index exists.

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

Entries are appended on each Run, capped at 20 (oldest evicted). The
sidebar renders the most recent first; clicking a re-run icon copies
the entry's parameters back into the inputs and triggers a Run.

No persistence — vanishes when the Streamlit process restarts.

## 4. Data model

### 4.1 New dataclasses

- `scripts/answer/contracts.py`: add `SlotDecision` per §3.4. The UI
  module and (eventually) #82's diagnostics work both consume it, so
  it lives in the public contracts module rather than as a
  module-private helper inside `composer.py`.
- `scripts/ui/state.py`: `QueryHistoryEntry` per §3.7.

### 4.2 No external schema changes

The strict `answer_with_citations.schema.json` does not change. The UI
renders existing data; the only contract change is internal to
`scripts/answer/composer.py`.

## 5. Key decisions

1. **Streamlit, not Gradio / FastAPI / a SPA.** Single-user local debug
   tool. Streamlit ships in ~300 lines, no JS, no template files,
   built-in expanders + JSON viewers + tables + sliders. Cost-benefit
   is clearly Streamlit.
2. **No Streamlit imports outside `debug_app.py`.** `panels.py`,
   `state.py`, and the new `SlotDecision` contracts stay pure-Python.
   Most of the logic is unit-testable without booting Streamlit.
3. **Compose-with-decisions as an additive API.** Existing
   `compose_segments(pack)` keeps its signature. The new
   `compose_segments_with_decisions(pack)` is the longer-form shape;
   the short form delegates to it. No breaking change for the answer
   CLI or the eval harness.
4. **Read-only on policy.** The UI does not let the user mutate the
   abstain-gate strictness, slot rules, or chunk corpus. Tuning policy
   is the next iteration's job (#82); v1 only *visualizes* current
   policy.
5. **Editable inputs limited to `top_k` + edition + source_type.**
   Other constraint fields (`excluded_source_ids`, `authority_levels`)
   are displayed read-only. Adds zero risk of "I changed something in
   the UI and the rest of the system thinks the constraint is still
   X."
6. **Session-only history, no persistence.** Single-user tool, no
   shared state, no need for an on-disk store. Restart wipes the
   slate; the user can copy queries to a notepad for permanence if
   desired.
7. **Missing-index = full-page error.** No half-rendered UI when the
   index doesn't exist. Same posture as the CLIs.

## 6. Alternatives considered

- **Gradio.** Better for single-input/single-output ML demo boxes;
  awkward for the multi-panel "show every stage" view. Rejected.
- **FastAPI + Vue/HTMX/plain HTML.** Full control, real frontend.
  Cost is 5–10× more code than Streamlit for a tool only the project's
  sole user will ever run. Rejected for v1; can be revisited if the UI
  ever needs to be shared / deployed.
- **Jupyter notebook.** Free, no web server. But the "type query → see
  results" loop is bad in notebooks (re-execute cells, scroll, repeat),
  and per-stage collapsibles are not native. Rejected.
- **Recompute slot decisions in the UI layer (read-only mirror of
  composer rules).** Avoids the contract change, at the cost of UI
  logic drifting from real composer rules. Rejected — drift risk is
  exactly the kind of debugging trap the UI is meant to eliminate.
- **Schema change to add slot decisions to
  `answer_with_citations.schema.json`.** Slot decisions are an
  internal pipeline concern, not part of the answer contract. The
  schema stays narrow.
- **Persisted query history (sqlite, JSON file).** Out of scope for
  v1. Adds complexity that single-session use doesn't justify.

## 7. Risks and open questions

1. **Streamlit version pinning.** Streamlit's API has historically had
   minor breaks (`st.experimental_*` rename cycles). Pin a known-good
   version range in `requirements.txt` (or wherever the project pins
   third-party deps; if there's no pinning convention yet, this PR
   can introduce one). Recommendation: `streamlit>=1.30,<2`.
2. **sqlite handle reuse on Streamlit's reload model.** Streamlit
   re-runs the script on every input change. Opening a fresh sqlite
   connection per Run is fine for our scale (hundreds of ms to query
   the index), but if it surfaces as a perf or file-handle issue,
   wrap the query in `@st.cache_resource` or pass the connection
   through `st.session_state`.
3. **Cross-platform launch path.** Windows + bash mix the project
   already uses (per `CLAUDE.md`). The launch command should be a
   single `streamlit run scripts/ui/debug_app.py` and not depend on
   shell-specific quoting.
4. **No automated end-to-end UI test.** v1 tests the pure helpers
   (`panels.py`, `state.py`, the new composer-decisions API). Driving
   Streamlit headlessly (e.g., via Playwright + the UI export of
   `streamlit hello`) is real complexity for marginal value on a
   personal tool. Acceptable risk; revisit if the UI ever ships
   beyond personal use.
5. **`SlotDecision` typing for the rejected tuple.** `(chunk_id,
   reason_code, detail)` as a 3-tuple is compact but unnamed. A named
   `RejectedCandidate` dataclass might be cleaner. Spec leaves the
   3-tuple in v1 to keep the new surface area small; revisit if
   downstream consumers (UI, #82's diagnostics) want named-field access.
6. **`top_k` upper bound.** Slider goes 1–25. The composer never reads
   beyond the top few items in practice (primary + 1–2 supporting), so
   higher `top_k` mainly affects the candidate-shaping panel and the
   evidence-pack contents in Debug mode. 25 is generous; bump if
   needed.

## 8. Next steps

This PR is **docs-only**. It lands the design spec for #91 and does
not close it. The implementation PR closes #91.

1. **This PR (docs-only).** Spec review and approval. Refs #91; does
   not close it.
2. **Implementation PR (closes #91).** Implement per §3 layout:
   composer-decisions contract addition (with new tests in
   `tests/test_composer_decisions.py`), the `scripts/ui/` package
   (`contracts.py`, `state.py`, `panels.py`, `debug_app.py`), the
   missing-index guard, and a short "Local debug UI" subsection in
   `docs/architecture_overview.md` (mirror to `docs/zh/`). Pin
   `streamlit>=1.30,<2` in `requirements.txt` (introduce the file if
   it doesn't exist).
3. **Manual verification.** Launch the app against the real
   `lexical.db`; run "attack of opportunity", "turn undead", and one
   abstain-expected query (e.g., the "warlock class progression"
   case from the gold set). Capture a screenshot or two of the Debug
   mode for the implementation PR's evidence block.
4. **Follow-up backlog (out of scope for both PRs):**
   - Wire #82's `gate_too_strict` / `retrieval_weak` sub-tag into the
     UI's Support assessment panel once #82 lands.
   - Consider sharing the `panels.py` helpers with
     `run_phase1_eval.py`'s Markdown report generator. Today they
     duplicate some formatting logic (citations table, signal table);
     consolidating is YAGNI until both consumers actually want the
     same shape.
   - Persisted query history (sqlite or JSON file) if and when the
     project grows beyond a single user.
