# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: D&D 3.5 Knowledge Chatbot

A private, personal D&D 3.5 knowledge chatbot. This repository is for designing a RAG system with citations over a private corpus of rulebooks.

## Current Phase

**Phase 1 — Core Implementation.** Phase 0 design is complete. Implementation is active.

- Ingestion pipeline (`scripts/ingest_srd35/`) is implemented and tested.
- Fixture corpus and golden tests are in place (`tests/fixtures/`, `tests/test_golden_ingestion.py`).
- Next: chunker, vector index, embedding pipeline.

Default to concrete implementation guidance. Design artifacts are still appropriate for new components before they are built.

## Project Constraints

- Private personal project; Phase 1 supports D&D 3.5 only.
- Only discuss other editions when explicitly asked for comparison.
- Design conservatively around copyright. Assume private local use of lawfully obtained materials.
- Prefer official rulebooks and supplemental materials as primary sources.
- Keep unofficial commentary, fan summaries, and homebrew separated from official sources.

## Primary Design Goals

1. Accurate rule retrieval
2. Verifiable citations and provenance
3. Clear separation of sources, editions, and authority levels
4. Modular architecture that allows model and vector DB swaps
5. Explicit abstention when evidence is insufficient

## Core Architecture Language

Use these terms consistently:
- **ingestion**: converts raw source files into normalized, source-traceable canonical documents
- **chunker**: converts canonical documents into retrieval-ready and citation-ready chunks
- **chunk**: the smallest unit used for retrieval and citation
- **citation anchor**: the metadata required to point back to book, page, section, and source
- **retrieval pipeline**: filtering → retrieval → reranking → answer composition → citation validation

Preferred pipeline vocabulary:
> Raw source → extraction → normalization → canonical corpus → chunked corpus → index → retrieval → answer generation → citation rendering

Do not collapse ingestion and chunking into one conceptual step unless explicitly discussing an implementation shortcut.

## Source Modeling

Whenever proposing schemas or architecture, distinguish at least:
`source_id`, `source_type`, `title`, `edition`, `authority_level`, `page range`, `section_path`, `version or checksum`, `chunk_id`, `citation_anchor`

Default source categories: `core_rulebook`, `supplement_rulebook`, `errata_document`, `faq_document`, `srd`, `curated_commentary`, `personal_note`

## Retrieval and Citation Principles

- Treat each chunk as both a retrieval unit and a citation unit.
- Prefer metadata filtering before semantic retrieval.
- Keep ruleset and source authority as hard filters where possible.
- Prefer abstain or insufficient-evidence behavior over speculation.
- Never fabricate page numbers, source coverage, or rule text.
- Prefer claim-level or paragraph-level citations, not only a trailing source list.

## Model-Selection Principles

Separate three roles: **answer model**, **embedding model**, **reranker (optional)**. Do not assume one model handles all three. Optimize for swapability and clear interfaces between components.

## Design Document Defaults

When producing a design artifact, use this structure (unless asked otherwise):
1. Goal
2. Scope and non-goals
3. Proposed design
4. Data model or schema
5. Key decisions
6. Alternatives considered
7. Risks and open questions
8. Next steps

For architecture choices, explain: what problem it solves, why it is preferred now, what tradeoff it introduces, and what would trigger revisiting it.

## Repository Layout

```
docs/                              Design documents (English)
  product_scope.md                 Phase 1 scope and non-goals
  architecture_overview.md         Pipeline diagram and component roles
  corpus_ingestion_design.md       Extraction and normalization stages
  chunking_retrieval_design.md     Chunking strategy and retrieval pipeline
  citation_policy.md               Citation anchor structure and rendering rules
  metadata_contract.md             Canonical field definitions (source_ref, locator, answer_segments)
  model_strategy.md                Answer model, embedding model, reranker roles
  evaluation_plan.md               Metrics, test set construction
  source_bootstrap_plan.md         Source admission contract and bootstrap strategy
  roadmap.md                       Phase plan and open tasks
  standards/
    pr_evidence.md                 PR evidence standard — pipeline changes must include inspectable evidence
  plans/                           Dated design and implementation planning notes
    YYYY-MM-DD-<slug>.md
  zh/                              Chinese mirror of all docs above (same filenames)

configs/
  source_registry.yaml             All ingestion sources must be registered here
  bootstrap_sources/
    <source_id>.manifest.json      Per-source bootstrap manifests

schemas/
  common.schema.json               Shared definitions (source_ref, locator, citation_anchor)
  canonical_document.schema.json
  chunk.schema.json
  answer_with_citations.schema.json

examples/                          Example JSON instances of each schema

scripts/
  fetch_srd_35.py                  Fetches raw SRD 3.5 HTML
  ingest_srd_35.py                 Entry point for SRD 3.5 ingestion
  ingest_srd35/                    Ingestion pipeline modules
  preview_fixtures.py              Preview fixture corpus diffs for PR evidence

tests/
  fixtures/                        Fixture corpus for golden ingestion tests
  test_golden_ingestion.py         Golden output tests (canonical document shape)
  test_ingest_srd_35.py            Unit tests for ingestion pipeline
  test_boundary_filter.py          Unit tests for boundary detection
  test_fetch_srd_35.py             Unit tests for fetcher

data/                              Local corpus files — not committed (see data/README.md)
```

Prefer updating an existing design doc over creating many new files. For architecture decision records, use `ADRs/ADR-xxxx-*.md`. Only create helper scripts, scratch files, or extra documents when clearly necessary or explicitly requested. Remove any temporary files before finishing.

## Working Style

- Be direct, concrete, and technically grounded.
- Surface assumptions explicitly.
- Separate facts, design recommendations, and open questions.
- Prefer the smallest architecture that preserves correctness, provenance, and future extensibility.
- When uncertain: state the uncertainty, list the most likely options, and recommend the next design question to resolve.

## What to Avoid

- Jumping into code when the user asked for design
- Mixing D&D 3.5 with other editions by default
- Assuming one model handles answer generation, embeddings, and reranking
- Proposing RAG without explicit citation anchors or provenance fields
- Using unofficial summaries as authoritative rules text
- Weak framing like "PDF → chunks → vector DB" — use the full pipeline vocabulary instead
