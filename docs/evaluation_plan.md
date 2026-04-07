# Evaluation Plan

## Goal

Define how the system's retrieval quality, answer accuracy, and citation correctness will be measured.

## Scope

- Covers: evaluation dimensions, test set construction, metrics
- Does not cover: specific model benchmarks (see model_strategy.md)

## Evaluation Dimensions

### 1. Retrieval Quality

Measures whether the right chunks are retrieved for a given query.

| Metric | Description |
|---|---|
| Recall@K | Fraction of relevant chunks in top-K results |
| Precision@K | Fraction of top-K results that are relevant |
| MRR | Mean Reciprocal Rank of the first relevant chunk |

**What counts as relevant:** a chunk that contains the rule passage needed to correctly answer the query.

### 2. Answer Accuracy

Measures whether the generated answer is factually correct per official D&D 3.5 rules.

| Metric | Description |
|---|---|
| Accuracy | Fraction of answers judged correct against a gold answer |
| Hallucination rate | Fraction of answers containing rule text not in retrieved chunks |
| Abstention precision | Fraction of abstentions that are genuinely unanswerable |
| Abstention recall | Fraction of unanswerable queries where the system correctly abstains |

### 3. Citation Quality

Measures whether citations are accurate and verifiable.

| Metric | Description |
|---|---|
| Citation accuracy | Fraction of cited page/section references that correctly locate the source text |
| Citation coverage | Fraction of rule claims in the answer that carry a citation |
| Spurious citation rate | Fraction of citations that do not support their associated claim |

## Test Set Construction

### Query Categories

1. **Direct rule lookup** — single rule, unambiguous answer (e.g., "How many bonus feats does a Fighter get at level 4?")
2. **Multi-source synthesis** — answer requires combining rules from multiple sections (e.g., "Can a grappled character cast a spell?")
3. **Ambiguous or conflicting rules** — PHB text conflicts with errata or FAQ
4. **Unanswerable queries** — rule not covered by Phase 1 sources (tests abstention)
5. **Out-of-edition queries** — 5e or 4e question posed to the system (tests edition filtering)

### Construction Process

- Manually author 50–100 queries with gold answers and gold source citations
- Include at least 10 unanswerable queries
- Include at least 5 queries that require errata or FAQ awareness
- Gold answers reference specific book, page, and section

## Open Questions

- Who validates gold answers? (Manual review required)
- What threshold on retrieval recall is "good enough" to move to implementation?
- How to handle queries where multiple valid answers exist (e.g., optional rules)?
