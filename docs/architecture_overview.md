# Architecture Overview

> **English** | [中文](zh/architecture_overview.md)

## 1. Purpose

This document defines the **high-level architecture** for the D&D 3.5e Knowledge Chatbot.

It is intentionally **design-oriented**, not implementation-oriented. The goal is to make module boundaries, data flow, and system responsibilities explicit before choosing concrete frameworks, databases, or deployment infrastructure.

## 2. Architectural intent

The system is intended to behave as a **source-grounded rules assistant**.

At a high level, the system should:

1. ingest curated D&D 3.5e source material
2. normalize it into a canonical corpus
3. split it into retrieval-ready and citation-ready chunks
4. index those chunks for retrieval
5. answer user questions from retrieved evidence
6. attach citations that point back to preserved source provenance

The architecture should prefer:

- provenance over convenience
- explicit module boundaries
- stable intermediate representations
- strict ruleset scoping
- abstention over unsupported fluency

## 3. System shape

The intended system shape is:

```text
Curated Sources
  -> Ingestion
  -> Canonical Corpus
  -> Chunking
  -> Embedding / Indexing
  -> Retrieval
  -> Answer Composition
  -> Citation Rendering
  -> User Response
```

This architecture separates **document preparation** from **runtime question answering**.

That separation matters because:

- source handling changes more slowly than retrieval strategy
- chunking strategy is likely to evolve over time
- citation quality depends on preserved provenance from earlier stages
- answer generation should consume curated evidence, not raw documents

## 4. Core modules

### 4.1 Source registry

The source registry tracks the corpus inventory.

Its responsibilities include:

- identifying which sources are in scope
- assigning stable source identifiers
- tracking source type and edition
- recording source status and notes
- distinguishing primary sources from future supplementary sources

The source registry is a **corpus control layer**, not a retrieval layer.

### 4.2 Ingestion

The ingestion module transforms raw source artifacts into normalized canonical documents.

Its responsibilities include:

- reading source materials
- extracting usable text and structure
- cleaning noise such as repeated headers or OCR artifacts
- preserving page and section provenance
- producing canonical document objects

Ingestion should not be tightly coupled to a single chunking policy.

### 4.3 Canonical corpus

The canonical corpus is the stable intermediate layer between raw sources and chunked retrieval units.

Its role is to provide:

- a normalized document representation
- structural metadata such as section paths and page ranges
- stable source provenance
- a reusable base for re-chunking or re-indexing

This layer exists so that chunking can evolve without requiring full re-extraction from source files.

### 4.4 Chunking

The chunking module converts canonical documents into retrieval-ready and citation-ready units.

Its responsibilities include:

- preserving semantic coherence
- respecting rule boundaries where possible
- preserving source provenance for every chunk
- assigning chunk-level metadata
- supporting chunk strategies that are aware of sections, entries, and tables

The chunking layer is a core quality determinant for retrieval and citation.

### 4.5 Indexing

The indexing layer prepares chunks for runtime retrieval.

Its responsibilities include:

- associating chunks with embeddings or other retrieval representations
- storing chunk metadata for filtering
- making chunks searchable by later retrieval logic

This layer should support future changes in embedding or hybrid retrieval strategy without invalidating the canonical corpus model.

### 4.6 Retrieval

The retrieval layer selects supporting evidence for a user question.

Its responsibilities include:

- interpreting the user query
- applying ruleset and source filters
- retrieving likely relevant chunks
- returning evidence candidates for answer composition

In Phase 1, retrieval should assume a **strict D&D 3.5e corpus boundary**.

### 4.7 Answer composition

The answer composition layer turns retrieved evidence into a grounded response.

Its responsibilities include:

- answering the user question from retrieved evidence
- distinguishing support from inference
- avoiding unsupported claims
- abstaining when evidence is weak or conflicting
- producing a citation-ready response structure

The answer layer should not invent source references that were not present in the retrieved evidence set.

### 4.8 Citation rendering

The citation layer formats provenance into user-visible references.

Its responsibilities include:

- mapping answer references to source metadata
- rendering source title and location information
- preserving traceability from answer back to source

Citation is not a cosmetic post-processing step. It is the visible output of provenance preserved across earlier layers.

## 5. Data lifecycle

The system uses a staged data lifecycle.

### Stage A — Raw source layer

Examples:

- PDF rulebooks
- text exports
- structured source text
- future errata documents

This layer is the original input and should remain distinct from downstream processed forms.

### Stage B — Canonical document layer

This layer contains normalized document objects derived from the raw sources.

A canonical document should preserve:

- source identity
- edition
- document structure
- section hierarchy when available
- page location metadata
- cleaned content blocks

### Stage C — Chunk layer

This layer contains the retrieval and citation units derived from canonical documents.

A chunk should preserve:

- chunk identity
- source identity
- parent canonical document identity
- chunk type
- section path
- page range
- chunk text

### Stage D — Retrieval result layer

This layer contains the subset of chunks selected as evidence for a user query.

Retrieval results should be treated as **candidate evidence**, not yet as trusted final claims.

### Stage E — Answer layer

This layer contains the generated grounded response and attached citations.

The answer layer must remain traceable to the retrieval result set.

## 6. Runtime path vs preparation path

The system has two major flows.

### 6.1 Preparation path

This is the slower corpus-building path.

```text
Source Registry
  -> Raw Source Intake
  -> Ingestion
  -> Canonical Corpus
  -> Chunking
  -> Indexing
```

This path is where corpus quality, provenance, and chunk quality are established.

### 6.2 Runtime question-answering path

This is the user-facing path.

```text
User Question
  -> Query Interpretation
  -> Retrieval
  -> Evidence Set
  -> Answer Composition
  -> Citation Rendering
  -> Final Response
```

This path should remain dependent on retrieved evidence rather than latent model memory.

## 7. Design principles

### 7.1 Canonical before chunked

The architecture should always preserve a canonical corpus layer before chunk generation.

### 7.2 Retrieval unit equals citation unit

As much as practical, the chunk should function as both:

- a retrieval unit
- a citation anchor

This keeps provenance stable and reduces ambiguity at answer time.

### 7.3 Source provenance is never optional

Every downstream object should be traceable back to a source.

### 7.4 Edition boundaries are structural, not advisory

Edition scoping should be encoded in the architecture and metadata model, not left to prompt wording alone.

### 7.5 Answering is constrained by evidence

The answer layer exists to synthesize retrieved evidence, not to replace it.

## 8. Phase 1 assumptions

The architecture assumes the following for Phase 1:

- private, single-user usage
- D&D 3.5e only
- curated corpus rather than open web retrieval
- design-first repository state
- citation as a first-class requirement

These assumptions reduce complexity and help prevent premature generalization.

## 9. Excluded architecture concerns for Phase 1

The following concerns are intentionally deferred:

- public multi-user system design
- authentication and tenancy
- live sync across multiple users
- production deployment topology
- scaling architecture
- plugin ecosystem or third-party extensions
- generalized support for many game systems

## 10. Key architectural boundaries

### Boundary A — Source boundary
Only intentionally selected D&D 3.5e corpus sources are considered in-scope.

### Boundary B — Canonical boundary
Raw documents and canonical documents are different objects and must not be conflated.

### Boundary C — Chunk boundary
Chunking is downstream from canonical normalization and may evolve independently.

### Boundary D — Evidence boundary
Retrieved chunks are the evidence set available to the answer layer.

### Boundary E — Citation boundary
User-visible citations must resolve to preserved provenance rather than freeform model output.

## 11. Future extension points

The architecture should leave room for future additions without forcing them into Phase 1.

Potential extension points include:

- errata and FAQ overlays
- reranking
- comparison mode across rulesets or editions
- support for structured table-aware retrieval
- source priority policies
- quote extraction policies

These should be added intentionally rather than assumed by default.

## 12. Open design questions

The following questions remain open and belong to later documents:

- What canonical document schema should be used?
- What chunk types are required for rules, spells, feats, and tables?
- How should citations be formatted in final answers?
- How should conflicts between primary text and later errata be represented?
- What evaluation standard determines whether retrieval is good enough?

## 13. Summary

In one sentence:

> The architecture is a staged, provenance-preserving RAG pipeline that turns curated D&D 3.5e source material into grounded answers with traceable citations.
