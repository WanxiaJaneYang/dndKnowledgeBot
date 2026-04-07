# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: D&D 3.5 Knowledge Chatbot

A private, personal D&D 3.5 knowledge chatbot. This repository is for designing a RAG system with citations over a private corpus of rulebooks.

## Current Phase

Design only. Default to analysis, design recommendations, and markdown artifacts. Only move into implementation when explicitly asked.

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

Default source categories: `official_rulebook`, `official_errata`, `official_faq`, `srd`, `commentary`, `homebrew`, `personal_note`

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
docs/                         Design documents
  product_scope.md            Phase 1 scope and non-goals
  architecture_overview.md    Pipeline diagram and component roles
  corpus_ingestion_design.md  Extraction and normalization stages
  chunking_retrieval_design.md  Chunking strategy and retrieval pipeline
  citation_policy.md          Citation anchor structure and rendering rules
  model_strategy.md           Answer model, embedding model, reranker roles
  evaluation_plan.md          Metrics, test set construction
  roadmap.md                  Phase plan and open tasks
configs/
  source_registry.yaml        All ingestion sources must be registered here
schemas/
  canonical_document.schema.json
  chunk.schema.json
  answer_with_citations.schema.json
examples/                     Example JSON instances of each schema
data/                         Local corpus files — not committed (see data/README.md)
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
