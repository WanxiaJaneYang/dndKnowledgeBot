# Model Strategy

> **English** | [中文](zh/model_strategy.md)

## 1. Purpose

This document defines the model roles and model-selection philosophy for the D&D 3.5e Knowledge Chatbot.

The purpose of this file is not to lock final implementation choices immediately. Its purpose is to prevent the project from collapsing multiple distinct model responsibilities into a single vague idea of `the model`.

## 2. Core principle

This project should distinguish between at least three model roles:

1. **Answer model**
2. **Embedding model**
3. **Optional reranker**

These roles solve different problems and should be evaluated separately.

## 3. Why role separation matters

If the project treats all model responsibilities as one decision, it becomes difficult to reason about:

- retrieval quality
- citation faithfulness
- answer quality
- cost and latency tradeoffs
- local deployment constraints
- future swapability

A strong answer model cannot compensate for poor embeddings forever, and a good embedding model cannot by itself produce grounded final answers.

## 4. Phase 1 model assumptions

Phase 1 assumes:

- open-source model preference
- private, personal usage
- D&D 3.5e-only source scope
- design-first planning rather than benchmark-first optimization
- grounded answering with citations as the top product priority

The model strategy should therefore optimize for:

- controllability
- faithfulness to retrieved evidence
- tolerance for mixed Chinese/English user interaction if needed
- future replaceability

## 5. Answer model role

The answer model is responsible for:

- reading the user question
- consuming the retrieved evidence pack
- producing a grounded answer
- attaching or preserving citation references
- signaling uncertainty or abstention when support is insufficient

The answer model should not be treated as the primary source of rules knowledge.

Its job is to **reason over retrieved evidence**, not to replace retrieval.

## 6. Answer model requirements

A Phase 1 answer model should ideally support most of the following:

- instruction following
- grounded summarization
- citation-aware output shaping
- stable behavior when asked to abstain
- reasonable long-context handling for evidence packs
- acceptable English rules-text comprehension
- acceptable Chinese instruction comprehension if the user asks in Chinese

## 7. Answer model selection criteria

The answer model should be evaluated against questions such as:

- Does it stay close to retrieved evidence?
- Does it invent unsupported rules details?
- Does it handle exception-heavy rules text carefully?
- Does it obey answer formatting constraints?
- Does it respect abstain instructions?
- Does it remain usable under local or semi-local deployment constraints?

## 8. Embedding model role

The embedding model is responsible for turning both:

- corpus chunks
- user queries

into vector representations that make retrieval possible.

Its role is not to answer questions. Its role is to help the retrieval system find the right evidence.

## 9. Embedding model requirements

A Phase 1 embedding model should ideally support:

- strong semantic retrieval for technical or rules language
- acceptable performance on short queries and medium-length chunks
- tolerance for named rules terms and semi-structured entries
- stable behavior for English rules text
- acceptable support for Chinese queries if bilingual interaction is expected

## 10. Embedding model selection criteria

The embedding model should be evaluated against questions such as:

- Does it retrieve the correct rule section for common rules questions?
- Does it distinguish related but non-identical mechanics?
- Does it handle short named-entity queries such as feat or spell names?
- Does it perform acceptably on structured entries and section fragments?
- Does it create too many semantically similar but incorrect matches?

## 11. Optional reranker role

A reranker is an optional intermediate component that helps reorder the initially retrieved candidate chunks.

Its job is to improve the final evidence set by pushing better-supported chunks higher and reducing weak or duplicate candidates.

A reranker may be useful if the base retrieval stage produces:

- too many semantically similar distractors
- too much duplication from overlapping chunks
- poor ordering between main rules and loosely related text

## 12. Reranker selection criteria

If a reranker is added later, it should be evaluated against questions such as:

- Does it improve top-ranked evidence quality?
- Does it reduce false positives?
- Does it improve support for exception-heavy questions?
- Does it reduce noise enough to justify its complexity?

## 13. Open-source preference

Phase 1 assumes an open-source-first direction.

This preference is motivated by:

- private personal deployment flexibility
- future local experimentation
- easier component swapping
- less dependence on a single hosted vendor

This project should still distinguish between:

- open-source model family choice
- local deployment feasibility
- actual model quality for this task

An open-source preference does not mean every open model will be equally suitable.

## 14. Model swapability

The architecture should assume model replacement is normal.

This means the rest of the system should avoid coupling to one model family wherever possible.

The design should allow the future implementation to swap:

- answer model
- embedding model
- reranker

with minimal changes to:

- canonical corpus
- chunk metadata
- citation policy
- evaluation structure

## 15. Model strategy and citation

The answer model must be constrained by citation policy.

This means the answer model should ideally:

- cite only evidence provided in the evidence pack
- avoid inventing source references
- signal when the evidence supports only a partial answer
- preserve the distinction between direct support and inference

A model that is fluent but citation-unreliable is a poor fit for this project.

## 16. Model strategy and abstention

Abstention behavior should be treated as a model requirement, not an afterthought.

The answer model must be able to:

- decline unsupported claims
- answer narrowly when only part of the question is supported
- explicitly say when the evidence is insufficient

This is especially important for rules questions because incorrect certainty is often more harmful than an incomplete answer.

## 17. Early evaluation philosophy

The project should not begin with large-scale benchmarking.

Instead, it should start with a small, focused evaluation set that checks:

- groundedness
- citation faithfulness
- exception handling
- abstain behavior
- bilingual query handling if relevant

Model decisions should be made against this task-specific bar rather than general leaderboard impressions alone.

## 18. Deferred decisions

The following decisions are intentionally deferred:

- exact answer model family and size
- exact embedding model choice
- whether reranking is required in the first implementation
- whether answer generation should be fully local from day one
- exact context window requirements
- exact performance targets for latency or hardware

## 19. Summary

In one sentence:

> The model strategy for this project should treat answer generation, embedding, and reranking as separate responsibilities and should prefer controllable, replaceable, citation-faithful components over generic fluency.
