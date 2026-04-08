# Corpus Ingestion Design

> **English** | [中文](zh/corpus_ingestion_design.md)

## 1. Purpose

This document defines the design of the **corpus ingestion layer** for the D&D 3.5e Knowledge Chatbot.

Its purpose is to describe how raw source materials become a **normalized, source-traceable canonical corpus** that can later be chunked, indexed, and cited.

This is a design document, not an implementation document.

## 2. Role of ingestion

Ingestion is the process that transforms raw source materials into structured canonical documents.

It is responsible for:

- accepting raw source artifacts
- extracting usable content
- cleaning and normalizing text
- preserving provenance
- producing stable document objects for downstream processing

Ingestion is **not** responsible for:

- final retrieval quality tuning
- answer generation
- citation rendering
- choosing a final chunk strategy

Those are downstream concerns.

## 3. Why ingestion is a separate layer

The project should explicitly separate:

- raw sources
- canonical documents
- chunks
- indexed retrieval units

This separation matters because:

- the same source may be re-chunked multiple times
- extraction and normalization logic changes differently from chunk strategy
- provenance must remain stable even if chunking changes
- citation quality depends on information preserved before chunking

The ingestion layer should therefore produce a reusable canonical corpus rather than directly producing final retrieval records only.

## 4. Phase 1 source assumptions

Phase 1 assumes a private, curated D&D 3.5e corpus.

Likely source categories include:

- core rulebook text maintained by the user for private personal use
- SRD-aligned material intentionally included in the corpus
- future errata or FAQ documents added as separately labeled sources

Phase 1 excludes uncontrolled external material such as:

- web forums
- fan wikis
- Reddit posts
- homebrew collections
- AI-generated summaries used as primary source material

## 5. Ingestion inputs

The ingestion layer should treat each source as an explicit tracked artifact.

Potential input forms include:

- PDF files
- OCR-derived text
- manually curated text exports
- markdown or plain text documents
- structured source records created later

The design should not assume that all sources are equally clean.

Some sources may:

- have strong structural signals
- have weak structure but clean text
- contain OCR noise
- contain tables or sidebars that require special handling later

## 6. Ingestion outputs

The primary output of ingestion is the **canonical document**.

A canonical document should be:

- normalized
- structured
- source-traceable
- stable enough to support re-chunking

A canonical document is not yet a vector index record and not yet a final answer unit.

## 7. Ingestion flow

The intended ingestion flow is:

```text
Source Registry Entry
  -> Raw Source Intake
  -> Extraction
  -> Cleaning / Normalization
  -> Structural Mapping
  -> Canonical Document Output
```

Each step should preserve or enrich provenance rather than discard it.

## 8. Source registry dependency

The ingestion layer depends on a source registry.

Before a source is ingested, it should have a tracked registry entry containing at least:

- source identifier
- source title
- ruleset / edition
- source type
- authority
- status
- notes

The source registry acts as the control surface for corpus admission.

## 9. Raw source intake

Raw source intake is the point where a source artifact is accepted into the project.

Its responsibilities include:

- linking the physical or logical artifact to a tracked source entry
- preserving original file identity where useful
- recording ingestion assumptions or caveats

The system should avoid treating anonymous text blobs as first-class sources.

## 10. Extraction

Extraction is the step that turns a raw artifact into usable textual and structural content.

Depending on source form, extraction may involve:

- reading embedded text from a digital document
- consuming OCR text
- reading structured text files
- preserving page boundaries when available

Extraction should aim to preserve:

- text content
- page locations
- headings or section markers
- obvious list or table boundaries when available

Extraction should not yet make irreversible assumptions about retrieval chunk size.

## 11. Cleaning and normalization

After extraction, the content should be cleaned into a consistent form.

Normalization goals include:

- removing repeated headers and footers when safe
- correcting obvious extraction noise
- standardizing whitespace and line breaks
- preserving meaningful formatting boundaries
- avoiding accidental loss of section meaning

The system should prefer **loss-minimizing normalization** over aggressive rewriting.

If a cleaning step risks destroying provenance or structure, it should be treated cautiously.

## 12. Structural mapping

Structural mapping is the step that identifies usable document structure.

Useful structure may include:

- book-level identity
- chapter or section hierarchy
- entry boundaries
- page ranges
- list blocks
- table blocks
- examples or sidebars

The goal is not to fully interpret every rule. The goal is to preserve enough structure for downstream chunking and citation.

## 13. Canonical document model

A canonical document should represent a normalized view of a source or source segment.

At a conceptual level, a canonical document should preserve:

- canonical document identifier
- `source_ref`
- `locator`
- document title when applicable
- cleaned content
- optional ingestion version or lineage metadata

Phase 1 should keep this contract thin. The design requirement is that the canonical document be stable and reusable, not overloaded with downstream retrieval or indexing details.

## 14. Provenance requirements

Provenance is mandatory.

At minimum, ingestion should preserve enough information to later support:

- source title citation
- edition scoping
- page-based reference where available
- section-path reference where available
- traceability from chunk back to source

If provenance is lost during ingestion, later citation quality will degrade.

## 15. Versioning and lineage

The design should assume that ingestion may be repeated over time.

Reasons include:

- improved extraction quality
- revised normalization rules
- source corrections
- new source versions
- better structural mapping

The ingestion model should therefore preserve lineage concepts such as:

- source version
- ingestion version
- canonical document version
- notes about known extraction issues

This does not require a final technical implementation yet, but it should be part of the conceptual model.

## 16. Treatment of tables, lists, and side material

Ingestion should preserve the existence of special structures even if later chunking decides how to use them.

Examples include:

- class tables
- equipment tables
- spell lists
- bullet lists
- sidebars
- examples

The ingestion layer does not need to solve final table retrieval on its own, but it should avoid flattening everything into unstructured text if recoverable structure exists.

## 17. Treatment of errata and FAQ materials

Future errata and FAQ documents should be treated as distinct source types rather than silently merged into older text.

Why this matters:

- the user may want to inspect the original text and the later clarification separately
- later correction layers may need explicit conflict policy
- citation should make the source of override or clarification visible

Phase 1 does not require a full errata overlay system, but the ingestion design should leave room for it.

## 18. Admission policy

Not every text artifact should automatically enter the corpus.

A source should be admitted only if:

- it is intentionally selected
- it belongs within D&D 3.5e scope for Phase 1
- its provenance is known
- it is appropriate for private personal use in this project

This project should prefer a smaller, cleaner corpus over a large uncontrolled one.

## 19. Failure modes to design against

The ingestion design should explicitly guard against:

- unknown source identity
- missing edition metadata
- broken page mapping
- over-aggressive cleaning that destroys structure
- accidental merging of different source layers
- silent provenance loss
- treating downstream chunking decisions as ingestion facts

## 20. Ingestion quality goals

A good ingestion outcome should satisfy most of the following:

- source is clearly identified
- text is readable and normalized
- page mapping is preserved where possible
- section structure is partially recoverable
- provenance is intact
- the canonical output is usable for multiple future chunk strategies

## 21. Deferred decisions

The following questions are intentionally deferred:

- What exact parser or extractor will be used?
- Will OCR correction be manual, automated, or mixed?
- How many canonical document granularities should exist?
- How should tables be represented structurally?
- Should one chapter map to one canonical document, or should the granularity be smaller?

These belong to later implementation or schema refinement work.

## 22. Summary

In one sentence:

> The ingestion layer converts curated D&D 3.5e source artifacts into a normalized canonical corpus that preserves provenance, structure, and reusability for later chunking and citation.
