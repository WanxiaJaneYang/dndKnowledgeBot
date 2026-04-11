# D&D 3.5 Knowledge Chatbot

> **English** | [中文](README.zh.md)

A private, personal RAG project for asking grounded questions about **Dungeons & Dragons 3.5e** rules and getting answers with **source citations**.

## Project status

This repository is in **early implementation** (Phase 1 bootstrap path in progress).

At this stage, the focus is:

- defining product scope
- defining corpus and source boundaries
- defining ingestion, chunking, retrieval, and citation strategy
- defining evaluation criteria

Design documents are still the source of truth, but ingestion and evaluation scaffolding are now implemented and used for regression evidence.

## Vision

The goal is to build a D&D rules assistant that:

- answers questions using retrieved rule text rather than unsupported model memory
- cites the supporting source for each answer
- stays within a clearly defined ruleset boundary
- abstains when evidence is insufficient or ambiguous

In Phase 1, the assistant is scoped to **D&D 3.5e only**.

## Why this project exists

General-purpose chat models often answer tabletop rules questions with a mix of:

- partial recall
- edition confusion
- invented certainty
- missing citations

This project is intended to solve that by treating the chatbot as a **source-grounded rules assistant**, not a generic fantasy chatbot.

## Core principles

### 1. Grounded over fluent
Answers must be supported by retrieved evidence. A less polished but grounded answer is better than a smooth hallucination.

### 2. Citation is a core feature
Citation is not a UI add-on. Retrieval and chunk design must preserve enough provenance for trustworthy source references.

### 3. Edition boundaries are strict
Phase 1 supports **D&D 3.5e only**. The system should not blend material from other editions unless future comparison mode is explicitly designed.

### 4. Private and personal use
This project is for private, personal use. It is not currently designed as a public-facing bot, shared rules platform, or commercial product.

### 5. Design before implementation
Architecture, corpus policy, and data contracts come before framework or deployment choices.

## Phase 1 scope

Phase 1 is intentionally narrow.

Included:

- single-user, private usage
- D&D 3.5e rules QA
- source-aware ingestion design
- chunking strategy for rulebooks and structured entries
- retrieval design for grounded answering
- citation-aware answer format
- abstain behavior when evidence is weak

Not included yet:

- multi-edition support
- homebrew or fan content
- campaign memory
- encounter simulation
- character optimization engine
- public hosting
- collaborative or multi-user features

## Planned document set

This repository is expected to grow around a small set of design documents.

- `docs/product_scope.md` — product boundaries, goals, and non-goals
- `docs/architecture_overview.md` — high-level system flow and module boundaries
- `docs/source_bootstrap_plan.md` — bootstrap source admission rules and first corpus slice
- `docs/metadata_contract.md` — shared vocabulary for source identity and locator semantics
- `docs/corpus_ingestion_design.md` — source handling and canonical corpus design
- `docs/chunking_retrieval_design.md` — chunking strategy, metadata, and retrieval flow
- `docs/citation_policy.md` — citation rules and answer provenance requirements
- `docs/model_strategy.md` — answer model, embedding model, and reranker strategy
- `docs/evaluation_plan.md` — success criteria and evaluation approach
- `docs/standards/pr_evidence.md` — minimum review evidence for pipeline PRs
- `configs/source_registry.yaml` — tracked corpus sources and metadata

## Initial product shape

At a high level, the intended product shape is:

1. ingest source documents into a canonical corpus
2. split canonical documents into retrieval-ready evidence units with preserved locators
3. index those units into a local vector-backed retrieval layer
4. answer user questions only from retrieved evidence
5. return a grounded answer with claim- or segment-level source references

## Source policy

The system is intended to work against a curated corpus rather than open web search.

Initial source priorities:

- `srd_35` as the bootstrap admitted source slice
- official D&D 3.5e rules text that the user lawfully owns or maintains for personal use
- structured supplementary source material added intentionally to the corpus
- future errata or FAQ material, if added, as separately labeled sources

The system should preserve source provenance at all times.

For the bootstrap slice, the repo now pins `srd_35` via
`configs/bootstrap_sources/srd_35.manifest.json`. Run `python scripts/fetch_srd_35.py`
to materialize the local source under `data/raw/srd_35/` without committing the raw SRD files.

## Answering policy

The assistant should:

- answer from retrieved evidence
- distinguish between direct evidence and inference
- avoid pretending certainty when the corpus does not support it
- cite supporting sources at the claim or segment level
- explicitly say when the evidence is insufficient

## Repository philosophy

This repo should stay small, legible, and design-driven.

Prefer:

- clear documents
- thin, explicit contracts
- named assumptions
- narrow phase goals

Avoid:

- premature framework decisions
- implementation-heavy scaffolding before scope is stable
- mixing design discussion with code experiments in the same files

## Next step

The bootstrap source is pinned, the metadata contract is unified, and the Phase-1 gold evaluation set is committed. The immediate next step is to implement the first end-to-end baseline (rule-aware chunking + retrieval + evidence-pack QA) against `srd_35`.
