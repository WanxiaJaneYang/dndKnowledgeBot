# Chunking and Retrieval Design

## Goal

Define how canonical documents are chunked for retrieval and how the retrieval pipeline operates.

## Scope

- Covers: chunking strategy, retrieval pipeline (filtering → retrieval → reranking)
- Does not cover: ingestion (see corpus_ingestion_design.md), answer generation (see citation_policy.md)

## Chunking

### Principles

- Each chunk is both a retrieval unit and a citation unit.
- Every chunk must carry a complete `citation_anchor` — no retrieval without citation capability.
- Chunks must not span multiple canonical documents (no cross-source chunks).

### Proposed Strategy

**Semantic chunking by rule block:**
- A rule block is a self-contained rules passage: a class feature description, a spell entry, a combat action, a condition definition, etc.
- Target size: 200–400 tokens.
- Overlap: minimal — only when a rule block slightly exceeds the target; never split a rule in half.
- If a rule block is too large (e.g., a full class description), split at sub-feature boundaries, not mid-sentence.

**Chunk metadata:**
Each chunk inherits `source_id`, `edition`, `authority_level`, `section_path`, and `page_range` from its parent canonical document, plus a unique `chunk_id`.

**Open:** exact tokenization method and target token range.

## Retrieval Pipeline

```
Query
  │
  ▼ 1. Metadata filtering (hard filters)
  │     - edition = "3.5"
  │     - authority_level ≤ threshold (configurable per query type)
  │     - source_type filter (exclude homebrew unless requested)
  │
  ▼ 2. Semantic retrieval
  │     - Embed query with embedding model
  │     - ANN search in vector index
  │     - Return top-K candidates
  │
  ▼ 3. Reranking (optional, Phase 2)
  │     - Cross-encoder reranker scores each candidate
  │     - Re-rank by relevance score
  │
  ▼ 4. Threshold filtering
        - Discard chunks below minimum relevance score
        - If no chunks remain → abstain
```

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Filter before retrieval | Yes | Prevents low-authority or wrong-edition chunks from polluting results |
| Citation at chunk level | Yes | Retrieval unit = citation unit; provenance is never lost |
| Abstention on low confidence | Yes | No answer is better than a fabricated one |

## Alternatives Considered

- **Fixed-size chunking (512 tokens)**: Simple to implement but frequently splits rule blocks mid-sentence, producing poor citation anchors.
- **Sentence-level chunks**: Granular but loses surrounding context needed for rule interpretation.
- **Post-retrieval edition filter**: Wastes compute on irrelevant chunks; metadata filtering is cheaper and more reliable.

## Risks and Open Questions

- Optimal chunk size requires empirical evaluation against real queries.
- Some rules (e.g., grapple rules) span multiple sections — how to handle cross-references?
- Reranker selection and whether it is needed in Phase 1.
- ANN index type and parameters (HNSW vs. flat index for small corpus).

## Next Steps

- Define evaluation queries to test chunking quality (see evaluation_plan.md)
- Prototype chunker on one PHB chapter
- Decide on vector DB and index configuration
