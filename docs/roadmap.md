# Roadmap

> **English** | [中文](zh/roadmap.md)

## Phase 0 — Design (current)

- [ ] Define product scope
- [ ] Define source bootstrap plan and admission contract
- [ ] Design corpus ingestion pipeline
- [ ] Design chunking and retrieval pipeline
- [ ] Define citation policy
- [ ] Define model strategy (roles and selection criteria)
- [ ] Define evaluation plan
- [ ] Freeze the admitted bootstrap source slice (`srd_35`)
- [ ] Build a 20-30 question gold set for that slice
- [ ] Align thin `source_ref` / `locator` / `answer_segments` contracts
- [ ] Validate provisional schemas against the slice

## Phase 1 — Core Implementation

**Sources:** Bootstrap with `srd_35`, then expand deliberately to PHB, DMG, MM, and later official errata / FAQ as the contracts hold up.

- [ ] Implement ingestion pipeline (extraction + normalization)
- [ ] Implement chunker
- [ ] Choose a baseline local vector index plus one embedding model and one answer model
- [ ] Set up vector index and embedding pipeline
- [ ] Implement retrieval pipeline (filter → retrieve → threshold)
- [ ] Implement answer generation with grounding constraint
- [ ] Implement citation rendering
- [ ] Implement abstention behavior
- [ ] Run evaluation against the Phase 0 test set

## Phase 2 — Quality Improvements

- [ ] Add reranker
- [ ] Expand source corpus (official supplements)
- [ ] Improve chunking for complex layouts (tables, multi-column)
- [ ] Add errata / FAQ override layer
- [ ] Extend the evaluation set

## Phase 3 — Interface

- [ ] Define target interface (CLI, Discord bot, web UI)
- [ ] Implement the chosen interface
- [ ] Add query logging for offline analysis

## Deferred / Out of Scope

- Multi-edition support
- Homebrew content integration
- Public hosting or multi-user access
- Real-time web retrieval
