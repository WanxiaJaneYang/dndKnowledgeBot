# Architecture Overview

## Goal

Describe the high-level system architecture for the D&D 3.5 Knowledge Chatbot.

## Pipeline

```
Raw source
   │
   ▼ extraction
Extracted text (per-page or per-section)
   │
   ▼ normalization
Canonical corpus  ──── canonical_document.schema.json
   │
   ▼ chunking
Chunked corpus  ──── chunk.schema.json
   │
   ▼ embedding
Vector index
   │
   ▼ retrieval pipeline
   │   1. Metadata filtering (edition, source_type, authority_level)
   │   2. Semantic retrieval
   │   3. Reranking (optional)
   │
   ▼ answer generation
Answer with inline citations  ──── answer_with_citations.schema.json
   │
   ▼ citation rendering
Final response to user
```

## Component Roles

| Component | Responsibility |
|---|---|
| Ingestion pipeline | Raw source → canonical corpus |
| Chunker | Canonical corpus → retrieval-ready chunks |
| Embedding model | Encodes chunks into vector space |
| Vector index | Stores and retrieves chunks by semantic similarity |
| Metadata filter | Hard-filters by edition, authority_level, source_type before retrieval |
| Reranker (optional) | Re-scores retrieved chunks for relevance |
| Answer model | Generates grounded answers from retrieved chunks |
| Citation renderer | Formats inline citations from citation anchors |

## Key Design Principles

- Ingestion and chunking are separate pipeline stages — do not collapse them.
- Each chunk carries a full citation anchor; retrieval and citation are inseparable.
- The answer model, embedding model, and reranker are separate components with clear interfaces.
- Metadata filtering happens before semantic retrieval, not after.
- The system must support abstention: if no chunk meets the quality threshold, respond "insufficient evidence."

## Open Questions

- Vector DB selection (Chroma, Weaviate, Qdrant, Pinecone, FAISS — see model_strategy.md)
- Extraction method for PDFs (pdfplumber, pymupdf, marker, etc.)
- Whether to run the answer model locally or via API
- Reranker inclusion in Phase 1 vs. Phase 2
