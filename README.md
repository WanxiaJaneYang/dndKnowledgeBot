# D&D 3.5 Knowledge Chatbot

A private, personal RAG-based chatbot for querying D&D 3.5 rules with verifiable citations and source provenance.

**Current phase: Design** — no implementation yet.

## Design Goals

1. Accurate rule retrieval from official sources
2. Verifiable, claim-level citations with full provenance
3. Clear separation of source types and authority levels
4. Modular architecture (swappable models and vector DB)
5. Explicit abstention when evidence is insufficient

## Pipeline

```
Raw source → extraction → normalization → canonical corpus
    → chunking → index → retrieval → answer generation → citation rendering
```

## Repository Layout

```
docs/           Design documents and architecture decisions
configs/        Source registry and configuration
schemas/        JSON Schemas for core data structures
examples/       Example instances of each schema
data/           Local corpus files (not committed — see data/README.md)
```

## Scope

- Phase 1: D&D 3.5 only (PHB, DMG, MM, SRD, official errata/FAQ)
- Private local use of lawfully obtained materials
- See [docs/product_scope.md](docs/product_scope.md) for full scope and non-goals
