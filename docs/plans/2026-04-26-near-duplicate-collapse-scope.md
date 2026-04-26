# Near-Duplicate Collapse — Scope and Required Signal

> **Status:** design (no code in this PR)
> **Target issues:** #68 (primary, closes), #34 (supersedes the deferred near-duplicate piece of its scope)
> **Author:** 2026-04-26

## 1. Goal

Decide what "near-duplicate" *means* in this project, and decide what minimum
signal the chunk / retrieval pipeline needs to support a near-duplicate
collapse step before any implementation lands.

This is a **design-only** deliverable. No code change.

This doc **deliberately does not file the implementation follow-up issues**.
It defines the exact issue shapes to open once one of the trigger
conditions in §5 fires. That is a deliberate deviation from #68's
acceptance criterion *"related follow-up issue(s) filed if the recommended
option requires ingest-side or evidence-pack-side work"* — the rationale
is in §5.

## 2. Scope and non-goals

### In scope

- A narrow, project-internal definition of "near-duplicate" suitable for
  Phase 1.
- An evaluation of three candidate signal mechanisms — ingest-side
  fingerprint, content-on-candidate, and late evidence-pack-side
  comparison.
- A recommendation, with rationale and tradeoffs.
- A forward plan: which follow-up issues this design produces, and the
  acceptance criteria those follow-ups need to meet — described in detail,
  filed only on trigger.

### Non-goals

- **No fuzzy / semantic similarity in v1.** No embeddings, no edit-distance
  thresholds, no token-set Jaccard. We are deliberately staying inside the
  "structural / chunking-induced repetition" definition below.
- **No containment / parent-child handling.** Hierarchical chunkers can
  produce a parent chunk whose text *contains* a child chunk's text. That
  is a different problem (containment, not equality), and equality on a
  normalized hash will not solve it. A parent-child evidence policy is
  out of scope for this design and will need its own doc when the
  hierarchical chunker lands.
- **No implementation in this PR.** No new files under `scripts/`, no
  schema changes, no contract changes. The deliverable is this document.
- **Not adjacent-chunk consolidation.** That work landed in #72 with its
  own rule (chains of hits contiguous in reading order, gated on
  bidirectional adjacency + section_path equality). Near-duplicate is a
  separate axis: two chunks can be near-duplicates without being adjacent.
- **Not broad same-document candidate grouping.** PR #65's "one chunk per
  document_id per group" idea was scoped out; PR #64's composite
  `(document_id, section_root)` grouping made it structural. Near-duplicate
  collapse *is* same-document by construction, but it operates at the
  individual-chunk level, not at group level.

## 3. Project-internal definition

For Phase 1, **near-duplicate means structural or chunking-induced
repetition**, not semantic similarity. Concretely, a near-duplicate pair is
two chunks where:

- they sit in the same `document_id`, **and**
- they have **identical** `section_path`, **and**
- they have the **same** `chunk_type` (so an errata or FAQ note can never
  collapse with a rule_section, even if the text were to match), **and**
- their normalized text differs only in formatting, leading/trailing
  whitespace, list markers, or a small prefix/suffix — i.e. the
  normalization function used by the fingerprint produces an identical
  output.

Common origins of such pairs in this corpus:

- **Chunk-overlap windows** — when the chunker emits overlapping chunks
  around a boundary, two chunks may carry the same core paragraph with
  slightly different surrounding context.
- **Re-ingestion of the same passage** — if the same source paragraph is
  pulled into two chunks under the same section (e.g. a sidebar that
  duplicates a paragraph from the running text), both chunks land at the
  same `section_path` with normalized-equal content.

What is **not** a near-duplicate under this definition:

- Two chunks that *talk about* the same rule but use different wording.
  That's a retrieval-relevance question, not a duplication question.
- A chunk and its summary / errata / FAQ entry. Those are separate
  citation units (per `docs/citation_policy.md`) — distinct `chunk_type`
  values prevent collapse even before the text is compared.
- Two chunks whose `section_path` differs (different sub-sections), even
  with textually identical content. They are different evidence units.
  The same heading-boundary discipline that gates adjacent-chunk
  consolidation applies here.
- A parent chunk and its child chunks under a hierarchical chunker. The
  parent's normalized text *contains* the child's; their hashes will
  differ. Solving "don't show parent + child as two pieces of evidence
  for the same passage" needs a parent-child evidence policy keyed on
  `parent_chunk_id`, not a near-duplicate hash. Out of scope here.

## 4. Signal options

A near-duplicate collapse step needs *some* signal that lets it compare two
candidate chunks. The current `LexicalCandidate` carries no comparable
content signal — only `chunk_id`, `match_signals`, `locator`, and (after
#69) adjacency links.

There are three plausible places to source the signal.

### Option 1 — Ingest-side fingerprint

Add a lightweight fingerprint to the chunk record at index time. Concrete
shape:

- New field on the chunk JSON, e.g. `dedupe_signature: str` or
  `normalized_content_hash: str`.
- Computed at chunking time as a stable hash of the chunk's content after
  a fixed normalization (lowercase, collapse internal whitespace, strip
  list markers and trailing punctuation, optionally drop the first heading
  line if it duplicates `section_path[-1]`).
- Stored as an indexed column in `chunk_metadata`.
- Returned by `_search_raw()` and promoted to a typed field on
  `LexicalCandidate`.

The collapse step is then pure equality on the citation-unit-gated key:

```
two candidates collapse iff
  same document_id
  AND same section_path
  AND same chunk_type
  AND same dedupe_signature
```

The `chunk_type` clause is the citation-unit gate — it prevents an errata
or FAQ entry from ever collapsing with a rule_section it might mirror.

**Pros:**
- Cheapest at query time — equality, no string comparison, no content load.
- Cleanest contract — fingerprint is a fixed-width string, no payload bloat.
- Future-proof — any consumer (evidence pack, future answer composer,
  debug CLI) can use the fingerprint for the same purpose.
- The normalization step is a single, auditable function; behaviour is
  inspectable and testable in isolation.

**Cons:**
- One-time cost: chunk schema bump, chunker change, full re-index.
- Hash collisions are theoretically possible. With a strong hash
  (SHA-256 truncated, or a 128-bit blake2b) the rate is negligible at
  Phase 1 corpus size, but worth noting.
- Normalization rules become a forward-compat concern: changing them
  invalidates existing fingerprints and forces a re-index.

### Option 2 — Content on `LexicalCandidate`

Carry chunk content (or a normalized excerpt) through the candidate
contract; the collapse step compares strings directly.

**Pros:**
- No ingest / schema change.
- The same content is needed by the evidence pack anyway, so it's already
  loaded somewhere downstream.

**Cons:**
- **Bloats `LexicalCandidate` significantly.** The contract grows from
  ~16 fields of cheap metadata to "metadata + N kilobytes of text per
  candidate." Every consumer pays the cost.
- **Blurs the retrieval / hydration boundary.** Currently `LexicalCandidate`
  is a metadata contract; content is fetched explicitly by
  `_fetch_content` at evidence-pack assembly time. Adding content to the
  candidate erodes that separation.
- String comparison on raw content is fragile to whitespace / formatting
  noise. We'd end up implementing the same normalization function as
  Option 1, but at query time, on every candidate.

**Verdict:** Not recommended. Listed for completeness.

### Option 3 — Late comparison at evidence-pack hydration

Defer the collapse step to `build_evidence_pack`. The evidence pack
already calls `_fetch_content` to hydrate representative chunks; a
near-duplicate pass can run there using the loaded content, applying the
same normalization function Option 1 would have run at ingest.

**Scope of this option:** exact normalized-content comparison, performed
late. It is *not* a path to fuzzy similarity, embeddings, or
containment — those problems still need their own designs. Option 3 is
the same comparison as Option 1, just done at query time on hydrated
content rather than at index time on a precomputed signature.

**Pros:**
- No ingest / schema change.
- Reuses an existing data path.
- Sits naturally at a layer that already knows about content.

**Cons:**
- **Comparison runs on every query, every time.** No precomputed signal
  to amortize against. Normalization happens at query time.
- The collapse decision lives downstream of the retrieval contract, so
  upstream consumers (re-ranker, future hybrid retrieval) don't see
  collapsed evidence — they see the un-collapsed candidate list.
- Changes the meaning of `EvidencePack.evidence` length: now a function
  of evidence-pack-side logic, not just retrieval-side state. Slightly
  harder to debug.

**Verdict:** Workable fallback for *exact normalized-content
comparison* if we want to ship before the chunker re-index lands.
Inferior to Option 1 in steady state for the same comparison; not a
substitute for any other duplicate-handling problem.

## 5. Recommendation

**Adopt Option 1 (ingest-side fingerprint) as the long-term path. Defer
implementation until a concrete trigger exists.**

Rationale:

- **Option 1's contract is the cleanest** and the cheapest at query time.
  The whole point of putting the signal at ingest is that retrieval
  becomes a simple equality check; the bookkeeping lives in the
  pipeline stage that already knows about chunk text.
- **Option 2 is rejected** outright — bloating `LexicalCandidate` to
  carry content is a worse tradeoff than re-indexing.
- **Option 3 is acceptable as a fallback** for the same exact-comparison
  semantics if we want to ship before the chunker re-index lands, but
  it's strictly inferior in steady state.

**Why defer implementation:** The current Phase 1 corpus is the SRD 3.5
fixture set. We don't yet have evidence that near-duplicates are a real
retrieval problem on this corpus. The right trigger to build Option 1
is:

- **The gold-set run (#24) flags "duplicate evidence" or "redundant
  citation" as a failure mode** under the current rule-based answer
  path (#23 / #74). This is the canonical signal that the strict
  abstain gate plus excerpt composer is producing duplicate-feeling
  output that a dedupe pass would clean up.

The trigger demonstrates that the cost of building Option 1 buys real
ranking / answer-quality improvement, rather than being speculative.
Building it now would be a textbook case of designing for hypothetical
future requirements.

**Note on the hierarchical chunker.** An earlier draft of this doc
listed the hierarchical chunker landing as a second trigger. That was
wrong — the hierarchical chunker produces *parent-child containment*,
not normalized-text equality. A parent chunk's text contains, but does
not equal, a child chunk's text; their fingerprints differ, and a
dedupe-by-signature pass cannot collapse them. The hierarchical chunker
will need its own parent-child evidence policy, not this mechanism.

**Filing the implementation issues.** They get filed when the trigger
fires, not on this PR's merge. Filing speculative implementation issues
ahead of evidence introduces backlog noise and freezes design choices
(field name, normalization rules, collapse-key shape) before they need
to be locked in.

## 6. Forward plan

This document closes #68. The implementation work is split into separate
issues, **opened only when triggered** (see §5). Their shapes:

1. **`feat(chunker): add dedupe_signature to chunk schema`** — chunker
   change, schema bump, normalization function, golden-test update,
   one-time re-index. **Acceptance criteria:**
   - Every chunk in `data/chunks/srd_35/` carries a `dedupe_signature`.
   - The normalization function is a single, importable function with
     direct unit tests.
   - **Distinct normalized texts in the current corpus produce distinct
     dedupe_signatures** (no collisions on real data).
   - **A small adversarial fixture set of known structural duplicates
     produces matching dedupe_signatures** — i.e. the function actually
     equates the cases it is meant to equate.
   - The chunk schema is bumped and `schemas/chunk.schema.json` is
     updated; existing golden tests are regenerated.

2. **`feat(retrieval): propagate dedupe_signature through LexicalCandidate`**
   — passthrough through `_search_raw`, `lexical_retriever.retrieve_lexical`,
   and `lexical_index.search_chunk_index`. Mirrors the shape of #69 (the
   adjacency-fields passthrough). **Acceptance criteria:**
   - `LexicalCandidate` gains `dedupe_signature: str | None` (None for
     legacy chunks indexed before issue 1 lands, then required after
     re-index).
   - Both constructor paths populate it.
   - Unit tests on both paths cover all-set and null cases.

3. **`feat(retrieval): collapse near-duplicate candidates by dedupe_signature`**
   — new step in the consolidation layer (or extend `consolidate_adjacent`
   into a more general `consolidate_candidates` that runs adjacent-chunk
   and dedupe passes). **Acceptance criteria:**
   - Output is `EvidenceSpan` with `merge_reason` extended from
     `Literal["singleton", "adjacent_span"]` to also include
     `"near_duplicate"`.
   - **The collapse key is `(document_id, section_path, chunk_type,
     dedupe_signature)` — chunk_type gate is required from day one** so
     errata / FAQ / rule-section distinctions can never be silently
     collapsed.
   - Interaction with adjacent-chunk consolidation is documented and
     tested (see §7).
   - Tests cover: trivial duplicate, formatting-only difference, distinct
     content not collapsed, errata vs rule_section not collapsed.

Issues 1 and 2 should land before issue 3 — same dependency shape as
#67 → #34's adjacent-chunk work.

## 7. Risks and open questions

- **Normalization rule choice.** The fingerprint's value depends on a
  good normalization function. Too aggressive (e.g., dropping all
  punctuation) and we collapse genuinely-different rules. Too loose and
  we miss obvious duplicates. The adversarial fixture set in issue 1's
  acceptance criteria is the lock-in mechanism.
- **Hash collisions.** With a strong hash (256-bit, or 128-bit blake2b)
  the rate is negligible at this corpus size. Still worth a property
  test in issue 1: *distinct normalized texts in the current corpus
  produce distinct dedupe_signatures.* Note this asks "no collisions on
  distinct content" — *not* "no two distinct chunks share a signature."
  Real near-duplicates are *expected* to share a signature; that is the
  point.
- **Citation-unit gating must be initial acceptance criteria, not a
  later concern.** If the dedupe step ships without gating on
  `chunk_type`, the first query that hits a rule and its errata as
  normalized-text equals will silently lose the authority-level
  distinction. The issue 3 acceptance criteria above bake the gate in
  from day one. (`authority_level` and `source_role` are not currently
  fields on `LexicalCandidate`; if they become available they should
  join the gate, but `chunk_type` is sufficient today because errata
  and FAQ entries already have distinct `chunk_type` values
  (`errata_note`, `faq_note`).)
- **Interaction with adjacent-chunk consolidation.** If we have three
  hits A, B, C where A and B are near-duplicates and B and C are
  adjacent in reading order, what wins — the dedupe collapse or the
  adjacency merge? Tentative answer: dedupe runs first (it's
  document-internal and conservative), then adjacency runs over the
  collapsed set. Worth confirming when issue 3 is filed.
- **Parent-child containment is a separate problem.** A hierarchical
  chunker emits a parent chunk whose normalized text *contains* a
  child chunk's text. Their dedupe_signatures will differ. The right
  primitive is "this chunk's parent_chunk_id is also in the evidence
  set; prefer one of them based on policy (parent for breadth, child
  for precision)." That belongs in its own design doc when the
  hierarchical chunker lands. It is **not** solved by Option 1 and
  should not be conflated with near-duplicate collapse.
