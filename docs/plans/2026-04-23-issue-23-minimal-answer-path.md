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

## 2. Scope and non-goals

### In scope

- Three composable units under `scripts/answer/`: support assessor, answer
  composer, citation binder; plus a `build_answer(pack)` pipeline function.
- One CLI entry point, `scripts/answer_question.py`, mirroring
  `scripts/retrieve_debug.py`'s text + `--json` shape.
- JSON output conforming to `schemas/answer_with_citations.schema.json`
  (strict fields), plus an optional augmented `debug` block carrying
  `PipelineTrace`, per-item match signals, and abstain trigger codes.
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
- A schema change to `answer_with_citations.schema.json`. The debug block
  lives alongside, not inside, the schema-validated portion.

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
  top-ranked item from a *different* `section_root` whose combined
  `exact_phrase_hits ∪ protected_phrase_hits` set is **not a subset**
  of the primary's hit set (i.e. it covers a query aspect the primary
  does not). If no such item exists but another sibling is available,
  fill Slot 2 with the next sibling instead. Otherwise leave empty.

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

### 3.5 CLI

`scripts/answer_question.py`:

```
python scripts/answer_question.py "attack of opportunity"
python scripts/answer_question.py "fighter bonus feats" --top-k 10
python scripts/answer_question.py "turn undead" --json
```

- Text mode: query block, abstain reason or segment list with inline
  citation markers and a citations table, plus a brief pipeline trace.
- JSON mode: strict `AnswerWithCitations` fields + `debug` block with
  `abstention_code` (when abstaining), `pipeline_trace`, and per-selected-item
  match signals. Callers that only want the schema-valid contract can
  drop the `debug` key before validating.
- Guard: if `data/index/srd_35/lexical.db` is missing, print the same
  error `retrieve_debug.py` prints and exit 1.

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

The trigger code itself lives under `debug.abstention_code` in JSON mode.

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

### 4.2 JSON shape

Strict portion validates against `schemas/answer_with_citations.schema.json`.
Augmented portion under `debug`:

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

4. **Augmented JSON with a `debug` block.** Strict schema fields preserved
   for the eval harness; `debug` sits alongside and carries the pipeline
   trace + abstain code. The schema is not changed.

5. **Canned abstention reason strings.** Machine-readable trigger code lives
   in `debug.abstention_code`; human-readable string satisfies the schema's
   `abstention_reason` requirement.

6. **No LLM.** Every decision in the pipeline is a function of
   `match_signals` + `candidate_shaping` output. This is what "inspectable
   baseline behavior" means in the #23 issue body.

## 6. Alternatives considered

- **LLM-based composer.** More realistic answers, but introduces API
  dependency, non-determinism, and hides baseline failures behind model
  behavior. Rejected for v1; can slot in behind `build_answer()` later
  without changing the contract.
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
   skipped or filled by fallback sibling), long content truncation, and
   end-to-end JSON schema validation.
4. Regenerate `examples/evidence_pack.example.json` and
   `examples/answer_with_citations.example.json` via the real pipeline.
5. Add a short "Answer stage" section to `docs/architecture_overview.md`
   and mirror to `docs/zh/architecture_overview.md`.
6. PR includes an evidence block per `docs/standards/pr_evidence.md`: CLI
   run against 3-4 queries (one clear grounded, one abstain, one edge case).
7. Merge closes #23; follow-up task for #24 consumes this pipeline as-is.
