# Roadmap

## Phase 0 — Design (current)

- [ ] Define product scope
- [ ] Design corpus ingestion pipeline
- [ ] Design chunking and retrieval pipeline
- [ ] Define citation policy
- [ ] Define model strategy (roles and selection criteria)
- [ ] Define evaluation plan and construct test set
- [ ] Select vector DB and models
- [ ] Finalize all schemas

## Phase 1 — Core Implementation

**Sources:** PHB, DMG, MM, SRD, official errata, official FAQ

- [ ] Implement ingestion pipeline (extraction + normalization)
- [ ] Implement chunker
- [ ] Set up vector index and embedding pipeline
- [ ] Implement retrieval pipeline (filter → retrieve → threshold)
- [ ] Implement answer generation with grounding constraint
- [ ] Implement citation rendering
- [ ] Implement abstention behavior
- [ ] Run evaluation against Phase 0 test set

## Phase 2 — Quality Improvements

- [ ] Add reranker
- [ ] Expand source corpus (official supplements)
- [ ] Improve chunking for complex layouts (tables, multi-column)
- [ ] Add errata/FAQ override layer
- [ ] Extend evaluation set

## Phase 3 — Interface

- [ ] Define target interface (CLI, Discord bot, web UI)
- [ ] Implement chosen interface
- [ ] Add query logging for offline analysis

## Deferred / Out of Scope

- Multi-edition support
- Homebrew content integration
- Public hosting or multi-user access
- Real-time web retrieval
