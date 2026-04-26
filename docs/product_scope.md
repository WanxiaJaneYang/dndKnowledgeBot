# Product Scope

> **English** | [中文](zh/product_scope.md)

## 1. Purpose

This project is a **private, personal D&D 3.5e knowledge chatbot** designed to answer rules questions using **retrieved source material with citations**.

The product is not intended to behave like a general-purpose conversational assistant. Its primary function is to act as a **source-grounded rules reference system**.

## 2. Product objective

The system should help the user:

- ask natural-language questions about D&D 3.5e rules
- retrieve the most relevant supporting rules text from a curated corpus
- receive a concise, grounded answer
- inspect source citations for verification
- detect when the evidence is insufficient, ambiguous, or conflicting

## 3. Target user

Phase 1 assumes a **single user**: the repository owner.

This means the product can optimize for:

- personal workflow
- private corpus management
- narrower operational constraints
- less concern about public distribution, multi-tenancy, or generalized onboarding

## 4. Product type

This is a **retrieval-augmented rules assistant**, not:

- a general fantasy chatbot
- a campaign companion
- a character builder
- a virtual tabletop assistant
- a creative writing assistant
- a public SRD portal

Its primary value comes from **grounded retrieval and verifiable citation**, not open-ended conversation.

## 5. Phase 1 scope

Phase 1 is intentionally narrow.

### In scope

- D&D **3.5e only**
- private, personal usage
- curated corpus ingestion (implemented; see `scripts/ingest_srd35/`)
- canonical corpus representation
- rule-aware chunking (baseline shipped; formatting-aware rewrite in flight)
- lexical-first retrieval (implemented; planned hybrid extension in Phase 2)
- citation-aware answer format
- abstain behavior for weak evidence
- design documents and schemas needed to support later implementation

### Out of scope

- support for other D&D editions
- cross-edition comparison
- homebrew and third-party content as first-class sources
- live web search
- campaign lore memory
- NPC or worldbuilding chat
- character sheet calculation or rules automation engine
- encounter simulation
- public deployment
- user accounts, permissions, or organization features

## 6. Ruleset boundary

The system must treat **D&D 3.5e** as a strict boundary in Phase 1.

Implications:

- retrieval must be scoped to 3.5e sources only
- answers must not quietly blend 3.0, 5e, Pathfinder, or forum-derived interpretations
- future support for multi-edition comparison must be designed explicitly rather than emerging accidentally

## 7. Source boundary

Phase 1 should prioritize a curated corpus of official or intentionally selected material relevant to D&D 3.5e.

### Initial source assumptions

Priority sources may include:

- core rulebooks the user maintains for private personal use
- SRD-aligned reference material, if intentionally included
- future errata or FAQ documents, if added as separately labeled sources

### Source exclusions in Phase 1

The following are excluded unless explicitly added in a later phase:

- forum posts
- Reddit discussions
- fan wikis
- homebrew rules
- AI-generated summaries as primary evidence
- unofficial optimization guides

## 8. Answering behavior

The assistant should answer in a way that is:

- grounded
- citation-backed
- concise
- explicit about uncertainty

### The system should do the following

- answer only from retrieved evidence when possible
- tie answer claims or segments to source citations
- distinguish between quoted or directly supported content and model inference
- abstain or narrow the claim when evidence is incomplete
- prefer precision over conversational smoothness

### The system should avoid the following

- answering purely from model memory when retrieval fails
- mixing unsupported interpretation with rule text without signaling it
- inventing citations
- presenting uncertain claims as settled rules

## 9. Citation expectations

Citations are a core product requirement.

At minimum, the product should preserve enough provenance to cite:

- source title
- ruleset / edition
- page range or source location
- section path or entry identity when available

A good answer should allow the user to inspect where the claim came from.

## 10. Corpus design expectation

The product requires an explicit distinction between:

- raw sources
- canonical documents
- chunks used for retrieval
- answer segments and citations

This separation is necessary because:

- the same source may be re-chunked over time
- chunk strategy will likely evolve
- citations should remain traceable to stable source metadata

## 11. Quality bar

A good Phase 1 answer should satisfy most of the following:

- retrieves relevant source material
- answers the actual question asked
- remains within D&D 3.5e scope
- includes citations
- avoids unsupported claims
- abstains when the corpus does not justify a strong answer

## 12. Success criteria for Phase 1

Phase 1 is successful if the project produces a stable design for a chatbot that can eventually:

- answer common D&D 3.5e rules questions from a private corpus
- provide source-linked citations
- avoid edition drift
- preserve provenance from ingestion through final answer
- define a clear path to implementation

## 13. Non-goals

The following are explicitly not goals for Phase 1:

- building a polished end-user app
- choosing final infrastructure or deployment stack
- benchmarking multiple frameworks in depth
- building a character rules engine
- solving every possible tabletop knowledge task
- making the bot broadly public or shareable

## 14. Design constraints

Phase 1 should assume the following constraints:

- implementation details are deferred until the design is stable
- repository documents should remain small and clear
- core terminology must stay consistent across files
- thin vertical slices should validate contracts before infrastructure choices are locked
- provenance and citation requirements must be designed before generation behavior

## 15. Key terminology

### Source
A raw or curated input artifact, such as a rulebook PDF or a structured source text.

### Canonical document
A normalized, structured representation derived from a source and prepared for downstream processing.

### Chunk
A retrieval-ready evidence unit derived from a canonical document. In Phase 1, a chunk is the default retrieval unit and default citation anchor, but not a hard invariant.

### Citation
A reference attached to a claim or answer segment that points back to preserved source provenance.

### Grounded answer
An answer whose claims are supported by retrieved source material.

## 16. Open questions for later phases

These are intentionally deferred and are not required to complete Phase 1 scope definition:

- Which open-source answer model will be used?
- Which embedding model will be used?
- Will reranking be required in the first implementation?
- How should tables be represented in chunking?
- How much direct quotation should the answer layer return?
- How should errata override or annotate earlier text?

## 17. Scope summary

In one sentence:

> Phase 1 is a private, single-user, D&D 3.5e-only RAG design project focused on grounded rules answers with source citations.
