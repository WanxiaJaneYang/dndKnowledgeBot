# Roadmap

> **English** | [中文](zh/roadmap.md)

## Phase 0 - Design (completed)

- [x] Define product scope
- [x] Define source bootstrap plan and admission contract
- [x] Design corpus ingestion pipeline
- [x] Design chunking and retrieval pipeline
- [x] Define citation policy
- [x] Define model strategy (roles and selection criteria)
- [x] Define evaluation plan
- [x] Freeze the admitted bootstrap source slice (`srd_35`)
- [x] Build a 20-30 question gold set for that slice
- [x] Align thin `source_ref` / `locator` / `answer_segments` contracts
- [x] Validate provisional schemas against the slice

## Phase 1 - Core Implementation (current)

**Sources:** Bootstrap with `srd_35`, then expand deliberately to PHB, DMG, MM, and later official errata / FAQ as the contracts hold up.

- [x] Implement ingestion pipeline (extraction + normalization) — `scripts/ingest_srd35/`
- [x] Add fixture corpus + golden outputs + preview evidence standard — `tests/fixtures/`, `docs/standards/pr_evidence.md`
- [x] Implement chunker — baseline section-passthrough strategy, `scripts/chunker/`, `tests/test_chunker.py`
- [x] Implement a lexical-first baseline retrieval pipeline (hard filters → normalization → BM25/FTS retrieval → evidence pack) — `scripts/retrieval/` (PR #49)
  - [x] Chunk-type prior in domain-aware scoring (PR #52)
  - [x] Structure-metadata indexing in the chunk index (PR #61)
  - [x] Section-aware candidate shaping layer keyed by `(document_id, section_root)` (PR #64)
  - [x] Chunk-adjacency fields (`parent_chunk_id`, `previous_chunk_id`, `next_chunk_id`) propagated through `LexicalCandidate` and `search_chunk_index` (PRs #67, #69)
  - [x] Recall-coverage tests expanded (PR #53)
- [x] Evidence-pack contract for retrieval output + retrieval-debug CLI — `scripts/retrieve_debug.py` (PR #66)
- [x] Implement v1 answer generation (rule-based excerpt composer with grounding constraint), citation rendering, and abstention behavior — `scripts/answer/`, `scripts/answer_question.py` (PR #74, issue #23)
- [ ] Implement v2 answer generation (LLM-backed prose composer over the same `EvidencePack` contract)
- [ ] Run evaluation against the Phase 1 gold set (`evals/phase1_gold.yaml`) — harness design landed (PR #79); first run pending

## Phase 2 - Quality Improvements

- [ ] Add vector / semantic retrieval for fuzzy phrasing and paraphrases
- [ ] Merge and rerank lexical + semantic candidates
- [ ] Add reranker
- [ ] Expand source corpus (official supplements)
- [ ] Improve chunking for complex layouts (tables, multi-column)
- [ ] Add errata / FAQ override layer
- [ ] Extend the evaluation set

## Phase 3 - Interface

- [ ] Define target interface (CLI, Discord bot, web UI)
- [ ] Implement the chosen interface
- [ ] Add query logging for offline analysis

## Deferred / Out of Scope

- Multi-edition support
- Homebrew content integration
- Public hosting or multi-user access
- Real-time web retrieval
