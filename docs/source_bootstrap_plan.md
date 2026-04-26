# Source Bootstrap Plan

> **English** | [中文](zh/source_bootstrap_plan.md)

## 1. Goal

Define the first admitted corpus slice for Phase 1 so later evaluation, ingestion, chunking, and retrieval work all target the same real source set.

The immediate question is simple:

> what source should enter the corpus first, under what admission rules, and in what directory layout?

## 2. Scope And Non-Goals

### In scope

- choosing the Phase 1 bootstrap source
- defining the bootstrap admission rule
- defining the minimum provenance bar for admitted sources
- defining the edition-writing rule for the bootstrap set
- defining the first-pass layout under `data/raw/`, `data/extracted/`, and `data/canonical/`

### Non-goals

- choosing the full long-term corpus
- deciding the final extraction toolchain
- admitting all core rulebooks at once
- solving later errata and FAQ layering
- deciding final chunking or retrieval implementation details

## 3. Proposed Design

Phase 1 bootstrap should admit **`srd_35` only**.

That means:

- the first admitted source slice is the D&D 3.5e SRD
- the first gold evaluation set should be written against SRD-covered questions
- the first ingestion spike should target SRD material first, not PHB / DMG / MM PDFs

Core rulebooks remain in the registry, but they are deferred to a later expansion after the bootstrap slice has proven the basic source, locator, and ingestion contracts.

The admission rule for the bootstrap slice is:

- the source must be intentionally selected in the registry
- the source must be inside the D&D 3.5e boundary
- the source must have clear provenance
- the source must have explicit `source_type`, `authority_level`, and `edition`
- the source must be stable enough to reproduce ingestion later

For bootstrap work, the project should reject or defer a source if:

- edition identity is ambiguous
- provenance is missing or weak
- the material is unofficial commentary, fan content, or AI-generated summary text
- the extraction path is so noisy that it prevents contract validation

## 4. Data Model Or Schema

### 4.1 Registry state model

Bootstrap source admission should use these states:

- `admitted_bootstrap`
  The source is in the first admitted corpus slice and may be used now.
- `planned_later`
  The source is intentionally in scope for a later Phase 1 expansion, but not yet admitted to the bootstrap slice.
- `excluded_phase1`
  The source is intentionally out of scope for the current phase.

No source currently uses `excluded_phase1`. The state is reserved so later explicit exclusions do not need a new vocabulary.

### 4.2 Provenance fields

Every admitted bootstrap source should preserve at least:

- `source_id`
- source title
- `edition`
- `source_type`
- `authority_level`
- a note describing the raw artifact or upstream source form
- enough locator information to support later citation
- notes about known extraction or structural caveats

For `srd_35`, the bootstrap expectation is source-native structure first. Page references become mandatory only when later admitted sources actually provide them.

### 4.3 Edition writing rule

The bootstrap set should write the edition label consistently as:

- `3.5e`

Do not mix:

- `3.5`
- `v3.5`
- `D&D 3.5`

inside the structured metadata contract.

### 4.4 Directory layout

Bootstrap corpus files should be organized by `source_id`.

```text
data/
|-- raw/
|   `-- srd_35/
|-- extracted/
|   `-- srd_35/
`-- canonical/
    `-- srd_35/
```

Guidelines:

- `data/raw/srd_35/` holds the raw admitted source artifact or curated source snapshot
- `data/extracted/srd_35/` holds extracted text or intermediate structured dumps
- `data/canonical/srd_35/` holds canonical document JSON outputs

## 5. Key Decisions

### Bootstrap with `srd_35`

`srd_35` is the first admitted source because it is the lowest-friction way to validate the product contract.

Compared with a PDF-first bootstrap, SRD-first gives the project:

- clearer source structure
- lower extraction noise
- easier locator design for non-paginated content
- a faster path to testing grounded answers, citation rendering, and abstain behavior

### Defer PHB / DMG / MM instead of admitting them immediately

The project should prove the contracts on one structured admitted source before it takes on OCR quality, page mapping, and layout recovery from scanned books.

### Keep `excluded_phase1` even though it is unused today

The vocabulary is still useful. It prevents later ad hoc wording when the project needs to record a deliberate exclusion.

## 6. Alternatives Considered

### Alternative A: bootstrap with one PHB chapter

This would test book-style page citations earlier.

Why not now:

- it introduces extraction and layout noise too early
- it makes locator and ingestion validation depend on PDF quality before the base contract is proven

### Alternative B: bootstrap with multiple narrow sources at once

This would broaden coverage sooner.

Why not now:

- it adds source-policy ambiguity before the first admission rule is stable
- it makes failures harder to localize

### Alternative C: admit all core books immediately

This could look closer to the eventual product corpus.

Why not now:

- it is too much surface area for the first contract-validation step
- it increases the risk of hiding source and locator problems under corpus size

## 7. Risks And Open Questions

- SRD structure is cleaner than PDF rulebooks, but it may still expose locator or extraction edge cases.
- SRD-first means the bootstrap slice will not test page-based citations yet.
- Some later Phase 1 questions may require PHB-only material, so the gold set must stay honest about SRD coverage.
- The next admitted source after `srd_35` is still open. A narrow PHB slice is the current likely candidate, but not yet a locked decision.

## 8. Next Steps

### Completed
- aligned the source registry to mark `srd_35` as `admitted_bootstrap`
- built the first gold evaluation set against SRD-covered questions (`evals/phase1_gold.yaml`, 30 cases)
- ran the first ingestion spike against `data/raw/srd_35/` (`scripts/ingest_srd35/`)

### Open
- expand beyond `srd_35` only after the bootstrap slice proves the contract is stable enough to carry a noisier source
