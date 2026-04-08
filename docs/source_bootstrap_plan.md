# Source Bootstrap Plan

> **English**

## 1. Purpose

This document defines the **Phase 1 bootstrap source plan** for the D&D 3.5e Knowledge Chatbot.

It answers one narrow but blocking question:

> what is the first admitted corpus slice that later evaluation, ingestion, chunking, and retrieval work should be built against?

This is not a plan for the entire long-term corpus. It is the admission contract for the first source set only.

## 2. Bootstrap decision

Phase 1 bootstrap should start with **`srd_35` only**.

This means:

- the first admitted source slice is the D&D 3.5e SRD
- the first gold evaluation set should be written against SRD-covered questions
- the first ingestion spike should target SRD material, not PHB / DMG / MM PDFs

Core rulebooks remain in the registry, but they are **not part of the bootstrap admission set** yet.

## 3. Why `srd_35` comes first

`srd_35` is the best bootstrap source because it is the lowest-friction way to validate the product contract.

Compared with a PDF-first bootstrap, SRD-first gives the project:

- clearer source structure
- lower extraction noise
- easier locator design for non-paginated content
- a faster path to testing grounded answers, citation rendering, and abstain behavior

The project should prove that the contracts work on one structured admitted source before it takes on OCR quality, page mapping, and layout recovery from scanned books.

## 4. Admission states

Phase 1 should use these source admission states in the registry:

- `admitted_bootstrap`
  The source is part of the first admitted corpus slice and may be used for evaluation and ingestion spikes now.
- `planned_later`
  The source is intentionally in scope for a later Phase 1 expansion, but it is not part of the bootstrap slice yet.
- `excluded_phase1`
  The source is intentionally out of scope for the current phase.

This state should answer a practical question:

> may this source enter the corpus right now?

## 5. Admission contract

A source may enter the bootstrap corpus only if all of the following are true:

- it is intentionally selected in the registry
- it is within the D&D 3.5e boundary
- its provenance is known well enough to cite and audit later
- its source type and authority are explicit
- its raw input form is stable enough to reproduce ingestion later

For bootstrap work, a source should be rejected or deferred if:

- edition identity is ambiguous
- provenance is missing or weak
- the source is unofficial commentary, fan material, or AI-generated summary text
- the extraction path is so noisy that it prevents contract validation

## 6. Provenance requirements

Every admitted bootstrap source should preserve at least:

- `source_id`
- source title
- `edition`
- `source_type`
- `authority`
- a note describing the raw artifact or upstream source form
- enough locator information to support later citation
- notes about known extraction or structural caveats

For `srd_35`, the bootstrap expectation is source-native structure first, page references only if a later admitted source provides them.

## 7. Edition writing rule

The bootstrap set should write the edition label consistently as:

- `3.5e`

Do not mix:

- `3.5`
- `v3.5`
- `D&D 3.5`

within the structured metadata contract.

## 8. Bootstrap directory layout

Bootstrap corpus files should be organized by `source_id`.

Expected layout:

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

This keeps the bootstrap slice easy to inspect and avoids mixing later sources into the first ingestion pass.

## 9. Bootstrap scope boundary

The bootstrap source plan does **not** mean SRD is the only source the project will ever support.

It means only this:

- the first vertical slice uses `srd_35`
- the first gold questions should be answerable from `srd_35`
- the first ingestion spike should prove the canonical contract on `srd_35`

PHB, DMG, and MM should remain registered as later planned sources, not silently admitted into the first slice.

## 10. Expansion trigger

The project should expand beyond `srd_35` only after the bootstrap slice has passed a basic reality check:

- the gold set exists
- the ingestion spike has produced inspectable canonical documents
- citation locators work for real examples
- retrieval and answer behavior are stable enough to expose the next real bottleneck

At that point, the likely next expansion is one narrow PHB slice rather than all core books at once.

## 11. Summary

In one sentence:

> Phase 1 bootstrap should admit `srd_35` first, use it to validate the first evaluation and ingestion slice, and defer PHB / DMG / MM until the source contract has been proven on that smaller corpus.
