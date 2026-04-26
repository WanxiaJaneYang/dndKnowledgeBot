# Chunking and Retrieval Design

> **English** | [中文](zh/chunking_retrieval_design.md)

## 1. Purpose

This document defines how the D&D 3.5e Knowledge Chatbot should:

- convert canonical documents into retrieval-ready units
- preserve enough provenance for citation
- retrieve evidence for user questions within a strict 3.5e boundary
- decide when evidence is sufficient to answer and when the system should abstain

This is a **design document**, not an implementation document.

## 2. Design objective

The chunking and retrieval layer exists to support a specific product behavior:

> given a D&D 3.5e rules question, retrieve the smallest useful set of source-grounded evidence blocks that can support a citation-backed answer.

The design should optimize for:

- semantic coherence
- strong provenance
- strict edition scoping
- good support for rule exceptions and structured entries
- answerability with citations
- graceful abstention when evidence is weak

## 3. Position in the system

This layer sits after ingestion and before answer composition.

```text
Curated Sources
  -> Ingestion
  -> Canonical Corpus
  -> Chunking
  -> Retrieval
  -> Answer Composition
  -> Citation Rendering
```

Chunking transforms canonical documents into stable evidence units.
Retrieval selects a subset of those units as evidence for answering.

## 4. Design assumptions

Phase 1 assumes:

- D&D 3.5e only
- private, personal use
- a curated corpus rather than open web search
- a rules assistant rather than a general free-form chatbot
- citation as a core product requirement

The retrieval layer should therefore behave more like a **rules evidence selector** than a general semantic search engine.

## 5. Core principle

### Chunk is the default retrieval unit and default citation anchor

A chunk is not merely a block of text for vector search.

In this project, a chunk should also function as the default evidence unit that can be attached to a user-visible citation.

That default should not be treated as a hard invariant. Some answers will need:

- multiple citations attached to one answer segment
- multiple finer citation locators derived from one retrieved chunk
- adjacent chunks combined to support one rule claim

This means chunk design must preserve:

- source identity
- edition identity
- page location when available
- section or entry identity when available
- enough local coherence to support interpretation

## 6. Why generic fixed-window chunking is not enough

A naive fixed-size chunker is likely to perform poorly on tabletop rules text because rules texts often contain:

- hierarchical headings
- definitions
- exceptions
- cross-references
- tables
- list structures
- entry-based formats such as feats, spells, skills, and class features

If a system splits only by token count, it may separate:

- a rule from its exception
- a spell name from its mechanics
- a class feature heading from the details that define it
- a table heading from the rows that matter

Phase 1 should therefore treat chunking as **rule-aware** rather than purely size-based.

## 7. Chunking goals

A good chunking strategy should satisfy most of the following:

- each chunk is understandable on its own or with minimal adjacent context
- each chunk maps back to a stable source location
- chunk size is small enough for precise retrieval
- chunk size is large enough to preserve the actual rule
- heading and body relationships are not lost
- structured entries are preserved as coherent units where possible
- retrieval can distinguish similar terms in different contexts

## 8. Chunk boundary policy

Chunk boundaries should prefer semantic and structural boundaries over arbitrary length boundaries.

The preferred boundary order is:

1. source boundary
2. document boundary
3. chapter or section boundary
4. entry boundary
5. paragraph or tightly related paragraph group
6. fallback size-based boundary

This means size-based splitting is a fallback, not the primary design rule.

## 9. Proposed chunk types

Phase 1 should support explicit chunk typing.

Proposed chunk types include:

- `rule_section`
- `subsection`
- `spell_entry`
- `feat_entry`
- `skill_entry`
- `class_feature`
- `condition_entry`
- `glossary_entry`
- `table`
- `example`
- `sidebar`
- `errata_note`
- `faq_note`

Not all of these need to be operational in the first implementation, but the design should leave room for them.

## 10. Section-aware chunking

Where source structure is available, chunking should preserve the relationship between:

- parent heading
- local heading
- body text
- page span

For example, a chunk should ideally know not just its text, but also that it came from something like:

`Combat > Attacks of Opportunity > Provoking an Attack of Opportunity`

This improves both retrieval precision and citation usefulness.

## 11. Entry-aware chunking

Certain content types should be treated as entries rather than generic paragraphs.

Examples:

- spells
- feats
- skills
- class features
- conditions
- glossary definitions

When an entry is structurally coherent, the system should prefer preserving the entry as a meaningful unit rather than slicing it into arbitrary windows.

If an entry is very large, the design may allow sub-entry chunking, but the relationship to the original entry must remain explicit.

## 12. Table handling

Tables are a known difficulty area.

The design should explicitly acknowledge that tables may not behave like prose.

Phase 1 should preserve the option to represent a table as one or more of the following:

- whole-table chunk
- table-with-caption chunk
- row-level chunks with inherited table metadata
- table plus derived structured representation

The design does not need to choose a final table strategy yet, but it should treat tables as first-class chunking cases.

## 13. Chunk metadata

Every chunk should carry enough metadata to support both retrieval and citation.

At minimum, a chunk should preserve:

- `chunk_id`
- `document_id`
- `source_ref`
- `locator`
- `chunk_type`
- `text`

Useful additional metadata may include:

- `parent_chunk_id`
- `previous_chunk_id`
- `next_chunk_id`
- `source_layer` such as base text or errata
- `tags`
- `created_from_strategy`
- `chunk_version`

`parent_chunk_id`, `previous_chunk_id`, and `next_chunk_id` are defined as optional string fields in `schemas/chunk.schema.json`. They are the adjacency links used by downstream consolidation and the evidence pack to reason about context without re-reading the canonical document. `None`/absent means the chunk is a boundary chunk (first or last in its section, or top-level with no parent).

Embedding vectors and other engine-specific index fields should live in derived index artifacts keyed by `chunk_id`, not in the stable chunk object itself.

## 14. Adjacency and lineage

A chunk should not be treated as an isolated blob.

The design should preserve some notion of neighborhood or lineage so that the system can later:

- inspect adjacent context
- merge nearby evidence when needed
- understand that two chunks came from the same larger entry
- avoid over-counting repeated nearby chunks as independent evidence

This is especially useful when a rule spans multiple short paragraphs.

## 15. Overlap policy

Chunk overlap may be used, but only as a controlled fallback.

Overlap is useful when:

- rule meaning spills over a boundary
- nearby sentences define an exception
- a heading and its first paragraph should remain retrievable together

However, excessive overlap can cause:

- duplicate retrieval hits
- inflated evidence confidence
- noisy context windows

The design should therefore treat overlap as a secondary mechanism, not the main coherence strategy.

## 16. Retrieval goals

A good retrieval stage should:

- stay within the D&D 3.5e source boundary
- prefer official or intentionally admitted material
- retrieve the most relevant evidence blocks
- avoid flooding answer generation with weak candidates
- preserve source identity for every candidate
- support abstention when evidence is weak or absent

## 17. Retrieval flow

The intended conceptual retrieval flow is:

1. interpret the user question
2. determine retrieval constraints
3. apply source and edition filtering
4. retrieve initial candidate chunks
5. optionally rerank or consolidate candidates
6. build an evidence pack for answer composition
7. decide whether the evidence is strong enough to answer

## 18. Query interpretation

Before raw similarity search, the system should attempt to understand the question at a lightweight level.

Relevant interpretations may include:

- rules question
- definition lookup
- exception lookup
- entry lookup
- comparison request within 3.5e source space
- ambiguous question requiring clarification or narrow answering

This interpretation does not need to be a heavy planner. It only needs to produce enough structure to guide retrieval.

## 19. Hard filters before semantic retrieval

In Phase 1, retrieval should apply hard filters before broad semantic matching where possible.

Examples of hard filters include:

- edition = 3.5e
- authority within admitted source policy
- excluded source layers if the user did not request them

This prevents the system from retrieving a semantically similar but out-of-scope text.

## 20. Phase 1 MVP retrieval policy

Phase 1 should start with a retrieval path that is deliberately narrow, controllable, and easy to debug.

The goal of this MVP is not to understand every fuzzy natural-language phrasing.

The goal is to prove that the system can reliably answer a narrow but important class of questions by showing:

- stable recall for core rules entries
- trustworthy citation anchors
- retrieval failures that are inspectable rather than mysterious

This means the MVP should be considered successful when it is strong on questions such as:

- `fighter hit die`
- `what are bonus feats`
- `attack of opportunity`
- `turn undead`

It may also handle some natural paraphrases, but questions such as `生命多少` or `血量多少` should not define the success bar for the first retrieval implementation.

## 21. Phase 1 retrieval mechanics

The Phase 1 retrieval path should stay lexical-first and domain-aware.

It should include:

- hard filters that lock edition and admitted source boundaries before scoring
- lightweight query normalization such as case folding, punctuation cleanup, and common format normalization
- domain-aware lexical retrieval as the main candidate generator, such as BM25 or FTS
- a small alias and protected-phrase layer for the most important rules terms

The alias layer should be intentionally small in the MVP.

It should cover the highest-value terms and fragile phrases rather than attempting full synonym expansion.

### 21.1 Composite retrieval score

Raw BM25 alone is not enough to rank rules chunks well, because a short entry that lexically matches a query is not always the best support. Phase 1 therefore combines BM25 with match-signal boosts and a chunk-type prior to produce a single composite score per candidate (see `scripts/retrieval/lexical_retriever.py`):

- **BM25 raw score** from the FTS index (lower-is-better)
- **Match-signal boosts** for section-path hits, exact-phrase hits, protected-phrase hits, and token overlap
- **Chunk-type prior** — a small per-type offset that reflects how rule-bearing a chunk tends to be

The chunk-type prior is keyed on the `chunk_type` enum in `schemas/chunk.schema.json`. Rule-bearing types receive the strongest boost, catalogue entries a moderate one, and illustrative or boilerplate types close to none:

- `rule_section` — top-level rule definitions, strongest signal
- `class_feature` — named mechanical features
- `feat_entry`, `skill_entry`, `spell_entry`, `condition_entry` — discrete catalogue entries
- `subsection` — general rule prose
- `errata_note` — authoritative corrections
- `table`, `faq_note`, `glossary_entry` — supporting reference material
- `paragraph_group` — contextual prose groupings
- `example`, `sidebar` — illustrative, rarely the primary answer
- `generic` — no signal (e.g. legal/license boilerplate)

The exact weights are an implementation detail and are tuned against the fixture corpus rather than declared policy. What matters at the design level is that retrieval scoring is explicitly aware of chunk type, not just BM25.

### 21.2 Structure metadata in the lexical index

The lexical index stores structure and adjacency metadata alongside the FTS-searchable content so retrieval can reason about section context and neighboring chunks without a separate lookup.

The index includes per-chunk columns for:

- `section_path_json` — the ordered section path for the chunk
- `path_depth` — depth of the section path
- `parent_chunk_id`, `previous_chunk_id`, `next_chunk_id` — adjacency links

These columns feed the section-path match signal, the shaping layer's `section_root` grouping key, and the evidence pack's per-item `section_root` field. A schema-version guard in `scripts/retrieval/lexical_index.py` rejects stale databases built before these columns were added.

## 22. Candidate retrieval

Initial retrieval should aim to produce a small candidate set rather than a large dump of weakly related text.

The candidate set should be large enough to cover:

- the main rule
- likely exception text
- the surrounding entry or section if needed

But it should remain small enough that answer composition can reason over it without losing precision.

## 23. Optional reranking

Reranking is conceptually useful but not mandatory to define Phase 1.

If present, reranking should help:

- push directly relevant chunks above loosely related ones
- favor chunks whose structure matches the question type
- reduce duplicates from overlapping or adjacent chunks

The design should allow an optional rerank stage without making the rest of the architecture depend on it.

## 23a. Candidate shaping

After the scored candidate list is produced (and optionally reranked), Phase 1 runs a lightweight shaping pass before evidence-pack assembly. See `scripts/retrieval/candidate_shaping.py`.

Shaping groups candidates by the composite key `(document_id, section_root)`, where `section_root` is the first element of the chunk's `locator.section_path`. Using a composite key prevents unrelated sections from different documents or sources from being merged just because they share a top-level heading name (for example, two different sources both named `Combat`).

Within each group, candidates preserve their original rank order. Groups are then sorted by the best (lowest) rank in each group, so the top-ranked evidence surfaces first but its sibling context stays attached.

Shaping is intentionally narrow:

- it does not drop candidates
- it does not rescore
- it does not merge across groups

It is a structural re-projection of the ranked list, not a second ranker. Heavier consolidation (merging adjacent chunks, collapsing near-duplicates) is still covered by Section 25.

## 24. Evidence pack construction

The retrieval layer should not pass raw search results directly into answer generation without normalization.

Instead, it should produce an **evidence pack** containing:

- the selected chunks
- their stable references
- provenance metadata
- any confidence or rank information that might help answer composition

The evidence pack is the handoff contract between retrieval and answer generation.

For Phase 1, the evidence pack should also be a debugging contract.

It should make it easy to inspect at least:

- which hard filters were applied
- which normalized query form was used
- which lexical signals or phrase matches contributed
- how candidates were ranked, grouped, or dropped

### 24.1 Phase 1 evidence pack shape

The concrete Phase 1 evidence pack is defined in `scripts/retrieval/evidence_pack.py`. It wraps the shaped retrieval output with enough context for answer generation to produce grounded, cited answers without re-querying the index, and carries a pipeline trace so retrieval behavior is inspectable via the debug CLI (`scripts/retrieve_debug.py`).

The pack has four top-level fields:

- `query` — the `NormalizedQuery` (raw query, normalized text, tokens, protected phrases, applied aliases)
- `constraints_summary` — a sorted dict of the hard filters that were applied: editions, source types, authority levels, excluded source ids
- `evidence` — a tuple of `EvidenceItem`s, globally sorted by rank so consumers can iterate as-ranked without re-sorting across groups
- `trace` — a `PipelineTrace` with `total_candidates`, `group_count`, and per-group `GroupSummary` entries (document_id, section_root, candidate_count)

Each `EvidenceItem` carries:

- `chunk_id`, `document_id`, `rank`
- `content` — the chunk text, hydrated from the index
- `chunk_type`
- `source_ref` and `locator` — the provenance needed for citation rendering (see `docs/metadata_contract.md` and `docs/citation_policy.md`)
- `match_signals` — exact-phrase hits, protected-phrase hits, section-path hit, token-overlap count
- `section_root` — the group key used by shaping, preserved on each item so consumers can reason about coverage
- adjacency — `parent_chunk_id`, `previous_chunk_id`, `next_chunk_id` (propagated from `LexicalCandidate`)

Adjacency links (`parent_chunk_id`, `previous_chunk_id`, `next_chunk_id`) are propagated from the upstream `LexicalCandidate` contract directly onto each `EvidenceItem`, so consumers (e.g. consolidation, the answer composer, debug tooling) can reason about chunk neighborhoods without re-querying the index.

## 25. Retrieval-time grouping and consolidation

The design should leave room for light grouping logic such as:

- collapsing near-duplicate chunks
- grouping chunks from the same section
- merging adjacent chunks when they form a single rule

This is important because multiple highly similar chunks do not necessarily mean multiple independent sources of support.

## 26. Phase 2 hybrid retrieval extension

After the lexical baseline is proven, the next retrieval step should be hybrid rather than lexical-only.

At that stage:

- lexical retrieval preserves terminology precision
- vector or semantic retrieval helps recover fuzzy phrasing, Chinese phrasing, and paraphrases
- merge and rerank logic combines both candidate streams
- lightweight question-type detection can be layered on top if it improves routing or ranking

This is the stage where questions such as the following should become materially more reliable:

- `生命多少`
- `血量多少`
- `5级 fighter 大概多少 hp`
- `体质16的人类战士有多少血`

In those cases, semantic retrieval helps bridge expressions such as `血量` or `生命` toward rules terms like `hit points` or `hp`, while lexical retrieval keeps class names, feature names, and mechanical terms anchored to the right rules text.

## 27. Answer support policy

An answer should normally be generated only when the evidence pack contains enough support to answer the user's question responsibly.

The system should distinguish between:

- **direct support**: the evidence states the answer or rule explicitly
- **supported inference**: the answer is not quoted directly but follows from the evidence
- **weak support**: the evidence is only loosely related
- **insufficient support**: the evidence does not justify a clear answer

## 28. Abstain behavior

The retrieval design must support abstention.

The system should abstain, narrow the claim, or explicitly mark uncertainty when:

- no relevant chunk is retrieved
- the retrieved chunks are too weakly related
- evidence appears contradictory and conflict policy is unresolved
- the answer would require unsupported memory rather than retrieved support

Abstention is a correct behavior, not a failure.

## 29. Failure modes to design against

The chunking and retrieval design should explicitly guard against:

- edition drift
- duplicate chunk inflation
- rule-exception separation
- heading loss
- table corruption
- retrieving a name without the mechanics that define it
- citation anchors that are too vague to verify
- answering from semantic similarity alone when no direct support exists

## 30. Quality bar

A good Phase 1 chunking and retrieval design should make it possible for the future system to:

- retrieve the correct rule section for common 3.5e questions
- preserve enough provenance for useful citations
- capture entry-like content cleanly
- avoid mixing out-of-scope sources
- support abstention when confidence is low

## 31. Deferred decisions

The following decisions are intentionally deferred:

- exact chunk size targets
- exact overlap size, if any
- final table representation strategy
- final local vector index or hybrid retrieval stack choice
- whether reranking is required in the first implementation
- the exact threshold for abstain vs answer

## 32. Summary

In one sentence:

> Phase 1 chunking and retrieval should treat rules text as structured evidence, not generic prose, and should optimize for precise grounded answering with trustworthy citations.
