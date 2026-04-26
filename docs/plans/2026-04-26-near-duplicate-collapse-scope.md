# Near-Duplicate Collapse — Scope and Required Signal

> **Status:** design (no code in this PR)
> **Target issues:** #68 (primary, closes), #34 (supersedes the deferred near-duplicate piece of its scope)
> **Author:** 2026-04-26

## 1. Goal

Decide what "near-duplicate" *means* in this project, and decide what minimum
signal the chunk / retrieval pipeline needs to support a near-duplicate
collapse step before any implementation lands.

This is a **design-only** deliverable. No code change. The follow-up
implementation issue is filed at the end of this doc.

## 2. Scope and non-goals

### In scope

- A narrow, project-internal definition of "near-duplicate" suitable for
  Phase 1.
- An evaluation of three candidate signal mechanisms — ingest-side
  fingerprint, content-on-candidate, and late evidence-pack-side
  comparison.
- A recommendation, with rationale and tradeoffs.
- A forward plan: which follow-up issues this design produces, and the
  acceptance criteria those follow-ups need to meet.

### Non-goals

- **No fuzzy / semantic similarity in v1.** No embeddings, no edit-distance
  thresholds, no token-set Jaccard. We are deliberately staying inside the
  "structural / chunking-induced repetition" definition below.
- **No implementation in this PR.** No new files under `scripts/`, no
  schema changes, no contract changes. The deliverable is this document.
- **Not adjacent-chunk consolidation.** That work landed in #72 with its own
  rule (chains of hits contiguous in reading order, gated on bidirectional
  adjacency + section_path equality). Near-duplicate is a separate axis:
  two chunks can be near-duplicates without being adjacent (and adjacent
  chunks are usually *not* duplicates of each other).
- **Not same-document dedup.** That was scoped out earlier — composite
  `(document_id, section_root)` grouping in PR #64 made it structural.

## 3. Project-internal definition

For Phase 1, **near-duplicate means structural or chunking-induced
repetition**, not semantic similarity. Concretely, a near-duplicate pair is
two chunks where:

- they sit in the same document, and
- their `section_path` is identical or very close (typically the same final
  segment), and
- their normalized text differs only in formatting, leading/trailing
  whitespace, list markers, or a small prefix/suffix.

Common origins of such pairs in this corpus:

- **Chunk overlap windows** — when the chunker emits overlapping chunks
  around a boundary, two chunks may carry near-identical core text with
  different surrounding context.
- **Paragraph regrouping** — different runs of the chunker may regroup the
  same paragraph under slightly different parents, producing two chunks
  whose body is the same paragraph.
- **Hierarchical chunk repetition** — a future hierarchical chunker will
  emit both a parent chunk and its child chunks, and a query that hits
  both will get duplicate evidence for the same passage.

What is **not** a near-duplicate under this definition:

- Two chunks that *talk about* the same rule but use different wording.
  That's a retrieval-relevance question, not a duplication question.
- A chunk and its summary / errata / FAQ entry. Those are intentionally
  separate citation units (per `docs/citation_policy.md`); collapsing them
  would lose authority-level distinctions.
- Two chunks whose section_path differs (different sub-sections). Even with
  textually identical content, they are different evidence units. The
  same heading-boundary discipline that gates adjacent-chunk consolidation
  applies here.

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

The collapse step is then pure equality on the fingerprint:

```
two candidates collapse iff
  same document_id
  AND same section_path
  AND same dedupe_signature
```

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

Defer the entire collapse step to `build_evidence_pack`. The evidence
pack already calls `_fetch_content` to hydrate representative chunks; a
near-duplicate pass can run there using the loaded content.

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

**Verdict:** Workable as a near-term lightweight path. Not the cleanest
end-state.

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
- **Option 3 is acceptable as a fallback** if we want to ship something
  before the chunker re-index lands, but it's strictly inferior in
  steady state.

**Why defer implementation:** The current Phase 1 corpus is the SRD 3.5
fixture set. We don't yet have evidence that near-duplicates are a real
retrieval problem on this corpus. The right trigger to build Option 1 is:

- the gold-set run (#24) flags "duplicate evidence" or "redundant
  citation" as a failure mode under the current rule-based answer path
  (#23 / #74), **or**
- the hierarchical chunker (designed in
  `docs/plans/2026-04-21-hierarchical-chunking-design.md`) lands and
  starts emitting parent + child chunks for the same passage.

Either signal demonstrates that the cost of building Option 1 buys real
ranking / answer-quality improvement, rather than being speculative.
Building it now would be a textbook case of designing for hypothetical
future requirements.

## 6. Forward plan

This document closes #68. The implementation work is split into separate
issues, **opened only when triggered** (see §5 above):

1. **`feat(chunker): add dedupe_signature to chunk schema`** — chunker
   change, schema bump, normalization function, golden-test update,
   one-time re-index. Acceptance: every chunk in `data/chunks/srd_35/`
   carries a `dedupe_signature`, and two chunks whose normalized text
   matches produce the same signature.
2. **`feat(retrieval): propagate dedupe_signature through LexicalCandidate`**
   — passthrough through `_search_raw`, `lexical_retriever.retrieve_lexical`,
   and `lexical_index.search_chunk_index`. Mirrors the shape of #69 (the
   adjacency-fields passthrough).
3. **`feat(retrieval): collapse near-duplicate candidates by dedupe_signature`**
   — new step in the consolidation layer (or extend `consolidate_adjacent`
   to a more general `consolidate_candidates` that runs adjacent + dedupe
   passes). Output is `EvidenceSpan` with `merge_reason="near_duplicate"`
   added to the existing `Literal["singleton", "adjacent_span"]`.

Issues 1 and 2 should land before issue 3 — same dependency shape as
#67 → #34's adjacent-chunk work.

## 7. Risks and open questions

- **Normalization rule choice.** The fingerprint's value depends on a
  good normalization function. Too aggressive (e.g., dropping all
  punctuation) and we collapse genuinely-different rules. Too loose and
  we miss obvious duplicates. We'll want a small adversarial test set
  before locking the rules in.
- **Hash collisions.** A 256-bit hash with a good distribution makes
  collision risk negligible at this corpus size. Worth a one-line
  property test (no two distinct chunks share a signature in the current
  corpus).
- **Interaction with adjacent-chunk consolidation.** If we have three
  hits A, B, C where A and B are near-duplicates and B and C are
  adjacent in reading order, what wins — the dedupe collapse or the
  adjacency merge? Tentative answer: dedupe runs first (it's
  document-internal and conservative), then adjacency runs over the
  collapsed set. Worth confirming when issue 3 is filed.
- **Errata and FAQ chunks.** Per `docs/citation_policy.md`, errata and
  FAQ entries are separate citation units and must not collapse with
  the rules they correct. The dedupe step needs to gate on
  `chunk_type` or `authority_level` to avoid losing those distinctions.
  This is a Phase-1.5 concern, not a Phase-1 blocker, but worth
  flagging now so the eventual normalization function doesn't quietly
  collapse them.
