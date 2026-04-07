# Model Strategy

## Goal

Define the roles of each model in the system and the criteria for selecting and swapping them.

## Scope

- Covers: answer model, embedding model, reranker roles and selection criteria
- Does not cover: prompting strategy (part of implementation), infrastructure/hosting

## Model Roles

The system separates three distinct model roles. No single model should be assumed to handle all three.

### 1. Embedding Model

**Job:** Encode chunks and queries into a shared vector space for semantic retrieval.

**Requirements:**
- Consistent encoding across the full corpus (same model version for chunks and queries)
- Sufficient vocabulary for rules text (domain-specific terminology)
- Fast inference — runs at indexing time (offline) and query time (online)

**Evaluation criteria:** retrieval recall on a held-out query set (see evaluation_plan.md)

**Open:** local model (e.g., `nomic-embed-text`, `bge-m3`) vs. API-based (e.g., OpenAI `text-embedding-3-small`)

### 2. Answer Model

**Job:** Generate a grounded, cited answer from retrieved chunks and the user query.

**Requirements:**
- Must follow a strict grounding constraint: answer only from provided context
- Must support claim-level citation in its output format
- Must produce an abstention response when context is insufficient
- Context window must accommodate top-K chunks plus query

**Evaluation criteria:** citation accuracy, grounding rate, abstention rate on unanswerable queries

**Open:** local model (e.g., Mistral, Llama 3) vs. API-based (e.g., Claude, GPT-4o); size vs. latency trade-off

### 3. Reranker (Optional — Phase 2)

**Job:** Re-score retrieved candidates before passing to the answer model to improve precision.

**Requirements:**
- Cross-encoder architecture (not bi-encoder)
- Operates on (query, chunk) pairs
- Should improve precision without requiring a larger top-K retrieval

**Open:** whether reranking is necessary for Phase 1 given small corpus size

## Interface Requirements

Each model role must expose a clean, swappable interface:
- Embedding: `encode(text: str) → List[float]`
- Reranker: `rerank(query: str, chunks: List[Chunk]) → List[Chunk]`
- Answer model: `generate(query: str, chunks: List[Chunk]) → AnswerWithCitations`

Concrete implementations plug into these interfaces. The pipeline does not depend on any specific model.

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Separate model roles | Yes | Different optimization targets; forces swapability |
| Grounding-only answer model | Yes | Fabrication is worse than abstention for a rules system |
| Reranker deferred | Phase 2 | Small corpus; evaluate if retrieval precision is sufficient first |

## Risks and Open Questions

- Local vs. API trade-off: latency, cost, privacy, and corpus size all influence this decision.
- Embedding model re-indexing: switching models requires re-embedding the entire corpus.
- Prompt design for the answer model is not covered here — that is an implementation concern.
