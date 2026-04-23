# Issue #23 — Minimal Answer Path with Citations and Abstain

> **Status:** design
> **Target issues:** #23 (primary), #24 (unblocks), #5 (closes rollup when both land)
> **Author:** 2026-04-23

## 1. Goal

Ship a thin, rule-based answer stage that consumes the existing `EvidencePack`
and produces one of:

- a **grounded answer** — a primary answer segment (excerpt of the top
  evidence chunk) with up to two supporting segments, each attached to a
  chunk-level citation; or
- an **abstain output** — a short reason string explaining why current
  evidence is insufficient.

The stage is deliberately rule-based (no LLM) so that Phase 1 can (a) answer
real questions end-to-end, (b) run the Phase 1 gold set under #24, and
(c) keep the baseline fully inspectable — every segment and every abstain
decision is a function of `match_signals` and `candidate_shaping` output.

> **This is an excerpt-based answer ("摘要式"), deliberately a validation
> scaffold — not the terminal design.** Segment text is always a chunk
> excerpt; the composer never synthesizes prose. The purpose is to
> unblock #24's gold-set evaluation and to surface retrieval / shaping /
> citation failures without mixing them with answer-generation noise.
> A real prose-synthesizing composer (LLM-backed, calling `build_answer()`
> over the same `EvidencePack`) is the intended successor in a later
> iteration; its shape is hinted at in §6 and kept open by keeping the
> `EvidencePack → AnswerResult` interface stable.

## 2. Scope and non-goals

### In scope

- Three composable units under `scripts/answer/`: support assessor, answer
  composer, citation binder; plus a `build_answer(pack)` pipeline function.
- One CLI entry point, `scripts/answer_question.py`, with three output modes:
  human-readable text (default), strict schema JSON (`--json`), and extended
  debug JSON (`--json-debug`).
- Two **distinct** JSON contracts:
  - `--json` — emits JSON that conforms exactly to
    `schemas/answer_with_citations.schema.json`. Nothing outside the schema
    is added. The eval harness can schema-validate the output directly.
  - `--json-debug` — emits a non-schema extended object carrying
    `PipelineTrace`, per-selected-item match_signals, and the abstain
    trigger code under a `debug` key. Explicitly declared non-schema-valid
    because the schema's top-level `additionalProperties: false` forbids
    unknown keys. Callers that need schema validation must use `--json`
    or strip `debug` before validating.
- Unit tests over synthetic `EvidencePack` fixtures and a CLI smoke test
  against the real `lexical.db`.
- Regenerated `examples/evidence_pack.example.json` and
  `examples/answer_with_citations.example.json` artifacts produced by the
  real pipeline (closes the small gap flagged on #22).

### Non-goals

- LLM-based answer synthesis. The composer never generates prose; segment
  text is always a chunk excerpt.
- Reranking, embeddings, or semantic similarity in the answer stage.
  Evidence order is taken as-ranked from `EvidencePack.evidence`.
- Multi-hop reasoning or cross-chunk inference beyond selecting at most
  two supporting segments.
- Conflict detection between evidence items (citation policy §13 — deferred).
- A schema change to `answer_with_citations.schema.json`. Debug information
  is carried only in the separate `--json-debug` CLI contract.

## 3. Proposed design

### 3.1 Pipeline

```
EvidencePack  →  assess_support  →  {grounded | abstain}
                    │
                    ├─ grounded  →  compose_segments  →  bind_citations  →  GroundedAnswer
                    └─ abstain   →                                          Abstention
```

`build_answer(pack)` orchestrates the three units and returns a single
`AnswerResult` (tagged union of `GroundedAnswer` or `Abstention`).
`answer_question.py` calls `retrieve_evidence(query)` (existing) to produce
the pack, then `build_answer(pack)` for the answer.

### 3.2 Support assessor — strict-signal gate

`assess_support(pack) → AssessmentResult` returns one of:

| Outcome | Trigger code | Condition |
|---|---|---|
| `abstain` | `empty_evidence` | `pack.evidence` is empty |
| `abstain` | `weak_signals` | top item has no `exact_phrase_hits`, no `protected_phrase_hits`, and `section_path_hit == False` |
| `grounded` | — | top item has ≥1 of the three strong signals |

`token_overlap_count` alone does **not** license a grounded answer. The
abstain bias is intentional; #24's gold run will surface the opposite
failure ("unnecessary abstain") as tagged data, which we use to justify
any future loosening.

### 3.3 Answer composer

On `grounded`, the composer emits 1–3 segments:

**Primary segment (always):**
- Source: `pack.evidence[0]` (top-ranked item).
- `text`: `item.content` if `len(content) ≤ 500`, else `content[:500].rstrip() + "…"`.
- `support_type`: `direct_support` when the primary has any
  `exact_phrase_hits` or `protected_phrase_hits`; `supported_inference`
  when only `section_path_hit` is true.
- `citation_ids`: one id pointing at the primary's chunk.

**Supporting segments — up to 2 slots, filled in order:**

- **Slot 1 (sibling):** next-ranked item in the primary's group (same
  `document_id` + `section_root`). Skip if no sibling exists.
- **Slot 2 (cross-section, then fallback sibling):** try first the
  best-ranked item from a *different* `section_root` whose combined
  `exact_phrase_hits ∪ protected_phrase_hits` set is **not a subset**
  of the primary's hit set (i.e. it covers a query aspect the primary
  does not). If no such item exists but another sibling is available,
  fill Slot 2 with the next sibling instead. Otherwise leave empty.

**Slot 2 — explicit resolution rules (deliberate simplifications):**

- **Distinctness comparison is limited to `exact_phrase_hits` and
  `protected_phrase_hits`.** `section_path_hit` (a boolean) is not
  included in the hit set used for subset comparison. Rationale: phrase
  hits are the signals that represent *what aspect of the query* a
  chunk addresses; `section_path_hit` represents *where in the corpus*,
  which the `section_root` grouping already handles.
- **Empty-primary-hit-set edge case.** When the primary has no phrase
  hits (its `section_path_hit` is the only strong signal), any
  cross-section item's hit set is trivially "not a subset" of the
  empty set. This is intentional — we *want* a supporting cross-section
  in this case, because the primary landed on the right section without
  textually quoting the query. The tie-break rule below keeps the
  choice deterministic.
- **Tie-break — always lowest global rank wins.** When multiple
  cross-section items qualify, pick the one with the smallest `rank`
  value (i.e. the best BM25 score). Rank is guaranteed unique within an
  `EvidencePack` by `retrieve_lexical`, so no further tie-breaking is
  needed.
- **The cost of this simplicity.** Slot 2 can occasionally pick a noisy
  cross-section item, especially when the primary's hit set is empty or
  small. #24's gold run is expected to surface this as a distinct
  failure tag ("slot-2 noise"), which is what justifies a later
  tightening — not speculative complexity now.

`support_type` for supporting segments uses the same rule as the primary.
Each supporting segment cites exactly one chunk.

### 3.4 Citation binder

`bind_citations(segments, pack) → (segments_with_citation_ids, citations)`:

- Assigns stable `citation_id`s (`cit_1`, `cit_2`, …) in segment order.
- Builds one `Citation` per selected evidence item:
  - `chunk_id`, `source_ref`, `locator` taken directly from the evidence item.
  - `excerpt`: same string used as `answer_segments[i].text` in v1.
    (Separate per-segment narrowing is a later enhancement — see
    citation policy §5 on locator narrowing.)
- Dedupes citations: if two segments cite the same `chunk_id` with the
  same excerpt, they share one `citation_id`. (Phase 1 composer will rarely
  hit this — different chunks → different citations — but the binder should
  be defensively deterministic.)

**Chunks vs. citations — definitions used by the binder and populated into
`retrieval_metadata`:**

- `retrieval_metadata.candidate_chunks` = number of candidates that entered
  shaping (i.e. `PipelineTrace.total_candidates`).
- `retrieval_metadata.selected_chunks` = number of **distinct** evidence
  chunks cited by the answer (count of unique `chunk_id` values across
  the `citations` array), not the number of citation objects. Multiple
  citations may point at the same chunk with different locators or
  excerpts — the schema permits this explicitly (see
  `answer_with_citations.schema.json` `citations[]` description), and
  `selected_chunks` counts the underlying chunk population, not the
  citation records.

### 3.5 CLI

`scripts/answer_question.py`:

```
python scripts/answer_question.py "attack of opportunity"
python scripts/answer_question.py "fighter bonus feats" --top-k 10
python scripts/answer_question.py "turn undead" --json
python scripts/answer_question.py "turn undead" --json-debug
```

Three output modes, mutually exclusive:

- **Text mode (default):** query block, abstain reason or segment list with
  inline citation markers and a citations table, plus a brief pipeline trace.
- **`--json` — strict schema mode:** output conforms exactly to
  `schemas/answer_with_citations.schema.json`. No `debug` key, no other
  additions; eval harness can schema-validate directly.
- **`--json-debug` — extended debug mode:** emits a top-level object with
  all strict-schema fields **plus** a top-level `debug` key carrying
  `abstention_code` (when abstaining), `pipeline_trace`, and
  per-selected-item match signals. Non-schema-valid by design — see §2
  for rationale. Callers that want the schema-valid subset must either
  use `--json` or strip `debug` before validating.

`--json` and `--json-debug` are mutually exclusive; passing both is a CLI
error.

- Guard: if `data/index/srd_35/lexical.db` is missing, print a clear
  error message to stderr and exit 1. Wording is not pinned to
  `retrieve_debug.py`'s current string; the contract is "clear stderr
  message + non-zero exit," not a specific phrase. Keeping the two
  CLIs consistent is encouraged but not required.

### 3.6 Abstain output

```json
{
  "query": "<raw query>",
  "answer_type": "abstain",
  "abstention_reason": "Insufficient evidence: no chunks retrieved for this query."
}
```

Canned strings:
- `empty_evidence` → "Insufficient evidence: no chunks retrieved for this query."
- `weak_signals` → "Insufficient evidence: retrieved chunks do not clearly match the query."

The trigger code itself is exposed only in `--json-debug` output, under
`debug.abstention_code`. `--json` carries only the schema-defined
`abstention_reason` string.

## 4. Data model

### 4.1 New dataclasses (`scripts/answer/contracts.py`)

```python
@dataclass(frozen=True)
class AnswerSegment:
    segment_id: str
    text: str
    support_type: Literal["direct_support", "supported_inference"]
    citation_ids: tuple[str, ...]

@dataclass(frozen=True)
class Citation:
    citation_id: str
    chunk_id: str
    source_ref: dict[str, Any]
    locator: dict[str, Any]
    excerpt: str

@dataclass(frozen=True)
class GroundedAnswer:
    query: str
    segments: tuple[AnswerSegment, ...]
    citations: tuple[Citation, ...]

@dataclass(frozen=True)
class Abstention:
    query: str
    reason: str
    trigger_code: Literal["empty_evidence", "weak_signals"]

AnswerResult = GroundedAnswer | Abstention

@dataclass(frozen=True)
class AssessmentResult:
    outcome: Literal["grounded", "abstain"]
    trigger_code: Literal["empty_evidence", "weak_signals"] | None
```

### 4.2 JSON shapes

Two distinct output shapes, one per CLI flag. The schema's top-level
`additionalProperties: false` forbids unknown keys, so these are separate
contracts — not "strict with optional extra fields".

**`--json` (strict, schema-valid):**

```json
{
  "query": "...",
  "answer_type": "grounded",
  "answer_segments": [...],
  "citations": [...],
  "retrieval_metadata": {
    "candidate_chunks": 12,
    "selected_chunks": 3
  }
}
```

This validates against `schemas/answer_with_citations.schema.json`.
`selected_chunks` counts distinct evidence chunks cited, not citation
records — see §3.4 for the definition.

**`--json-debug` (extended, NOT schema-valid):**

```json
{
  "query": "...",
  "answer_type": "grounded",
  "answer_segments": [...],
  "citations": [...],
  "retrieval_metadata": {
    "candidate_chunks": 12,
    "selected_chunks": 3
  },
  "debug": {
    "abstention_code": null,
    "pipeline_trace": {
      "total_candidates": 12,
      "group_count": 3,
      "groups": [...]
    },
    "selected_items": [
      {"chunk_id": "...", "rank": 1, "match_signals": {...}, "role": "primary"},
      {"chunk_id": "...", "rank": 3, "match_signals": {...}, "role": "sibling"}
    ]
  }
}
```

Callers that want schema validation from `--json-debug` output must pop the
`debug` key before validating. The `#24` eval harness is expected to use
`--json-debug` and split the debug block out for failure tagging.

## 5. Key decisions

1. **Strict-signal abstain gate (Policy A).** Abstain unless the top item has
   at least one of `exact_phrase_hit`, `protected_phrase_hit`, or
   `section_path_hit`. Token overlap alone never licenses an answer. Rationale:
   conservative by design; #24 can surface "unnecessary abstain" as its own
   failure tag, which is a better signal than guessing thresholds now.

2. **Length-cap truncation (Strategy B) for excerpts.** `item.content` if
   ≤ 500 chars, else truncate. Defer hit-anchored windowing until #24 shows
   it's needed.

3. **Supporting-segment policy B.** Siblings first, then one distinct-signal
   cross-section item, then a fallback sibling. "Distinct signals" = hit
   set of cross-section item is not a subset of the primary's hit set.

4. **Two separate JSON CLI contracts, not one schema+debug hybrid.**
   `--json` is strict-schema; `--json-debug` is extended and declared
   non-schema-valid. The schema's top-level `additionalProperties: false`
   forbids adding a `debug` key alongside schema fields, so a single
   "schema-plus-extras" output would silently fail validation. Keeping the
   two shapes distinct makes each contract honest about what it guarantees.
   The schema itself is not changed.

5. **Canned abstention reason strings.** Machine-readable trigger code
   appears in the `--json-debug` output under `debug.abstention_code`;
   the human-readable string satisfies the schema's `abstention_reason`
   requirement in `--json` output.

6. **No LLM in v1 — validation scaffold only.** Every v1 decision is a
   function of `match_signals` + `candidate_shaping` output. This is what
   "inspectable baseline behavior" means in the #23 issue body. The
   intentional cost is that answers read as stitched excerpts, not prose.
   A prose-synthesizing composer is the planned successor and will consume
   the same `EvidencePack`, so the interface is stable across the transition.

## 6. Alternatives considered

- **LLM-based composer (planned for v2, not rejected).** Real prose
  synthesis over the same `EvidencePack` — the actual target for the
  project. Deliberately deferred past v1 because (a) gold-set evaluation
  needs to distinguish retrieval/shaping/citation failures from
  answer-generation variance, and a rule-based composer isolates the
  former; (b) once #24 produces a tagged baseline, it becomes a fixed
  reference against which the LLM composer can be scored. Follow-up
  tracked as: introduce an `LLMAnswerComposer` that implements the same
  `build_answer(pack) → AnswerResult` interface behind a flag, so the
  CLI and eval harness can A/B the two composers without contract churn.
- **Policy B/C abstain gates** (token-overlap floors, composite scores).
  Let more queries through, at the cost of weaker guarantees. Reject now;
  revisit after #24.
- **Hit-anchored excerpt windowing (Strategy C).** Better excerpt quality,
  more logic. Deferred; revisit if #24 surfaces "buried relevant passage"
  failures.
- **Sections-as-segments shape.** One segment per candidate group. Loses
  the primary/supporting distinction that makes citation policy §10
  (direct vs supported_inference) cleanly expressible per segment.
- **Schema change to add `abstention_code`.** Would make the JSON strictly
  richer, but the schema belongs to the external contract. Keeping
  diagnostics out of the schema avoids churn and keeps `answer_with_citations`
  answer-model-agnostic.
- **Single `--json` output mixing schema fields and a `debug` block.**
  Rejected because the schema sets `additionalProperties: false` at the top
  level. A mixed output would fail schema validation, so the "strict with
  optional extras" framing is not actually available. The only way to keep
  one flag is to either change the schema (rejected, see above) or wrap
  the schema-valid payload under a key (e.g. `{"result": ..., "debug": ...}`),
  which breaks the expectation that `--json` emits the answer object
  directly. Two flags with two distinct contracts is the cleanest option.

## 7. Risks and open questions

1. **Over-abstain rate on paraphrased queries.** Policy A will reject queries
   like "how do fighters pick extra feats?" when the SRD uses "bonus feat."
   Mitigation: this is exactly what #24 is meant to measure; the
   "unnecessary abstain" tag makes it actionable.
2. **Primary excerpt can still be long.** 500 chars is a guess; SRD
   chunks are usually smaller, but a multi-paragraph chunk will hit the
   cap and lose context. Addressable by (a) tightening the cap, or
   (b) switching to Strategy C (hit-anchored window).
3. **Cross-section supporting slot may surface noise.** "Distinct signals"
   is a weaker proxy for "complementary" than the semantic concept.
   Fallback to sibling exists; #24 will tell us whether slot 2 earns
   its keep.
4. **Citation excerpt equals segment text in v1.** Citation policy §5
   hints that citations may narrow within a chunk. Not implemented here;
   `excerpt` simply duplicates segment text. Revisit when the composer
   gets smarter.
5. **No conflict detection (policy §13).** If two pieces of evidence
   disagree, the composer currently stacks both in order of rank and
   does not flag the conflict. Out of scope for #23.

## 8. Next steps

1. Open PR branch `issue-23-minimal-answer-path` off master.
2. Implement per §3 layout: contracts → support assessor → composer →
   citation binder → pipeline → CLI.
3. Write unit and pipeline tests covering: empty evidence, exact-phrase
   hit on top, section-path-only hit on top, token-overlap-only on top
   (abstain), primary + 2 siblings, primary + sibling + distinct-signal
   cross-section, primary + sibling + subset-signal cross-section (slot 2
   skipped or filled by fallback sibling), long content truncation,
   `--json` output validates against `answer_with_citations.schema.json`,
   and `--json-debug` output validates against the same schema **after**
   popping the `debug` key.
4. Regenerate `examples/evidence_pack.example.json` and
   `examples/answer_with_citations.example.json` via the real pipeline.
5. Add a short "Answer stage" section to `docs/architecture_overview.md`
   and mirror to `docs/zh/architecture_overview.md`.
6. PR includes an evidence block per `docs/standards/pr_evidence.md`: CLI
   run against 3-4 queries (one clear grounded, one abstain, one edge case).
7. Merge closes #23; follow-up task for #24 consumes this pipeline as-is.
8. **v2 follow-up (out of scope for this PR, but queued):** introduce an
   `LLMAnswerComposer` that implements the same `build_answer(pack) →
   AnswerResult` interface. Once #24 produces a tagged baseline, the
   LLM composer can be evaluated against the same gold set and the same
   failure tags. Open a new issue for this after #24 lands; do not start
   before the rule-based baseline's failure profile is recorded — the
   whole point of the v1 scaffold is to give the LLM composer something
   to be measured against.
