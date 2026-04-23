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
3. split it into retrieval-ready evidence chunks
4. derive index artifacts from those chunks for retrieval
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
  -> Indexing
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
- structural metadata such as section paths and source-native locators
- stable source provenance
- a reusable base for re-chunking or re-indexing

This layer exists so that chunking can evolve without requiring full re-extraction from source files.

### 4.4 Chunking

The chunking module converts canonical documents into stable evidence objects for retrieval and citation.

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

Index artifacts are derived from chunks. They should be replaceable without redefining the stable chunk contract.

This layer should support future changes in embedding or hybrid retrieval strategy without invalidating the canonical corpus model.

### 4.6 Retrieval

The retrieval layer selects supporting evidence for a user question.

Its responsibilities include:

- interpreting the user query
- applying ruleset and source filters
- retrieving likely relevant chunks
- returning evidence candidates for answer composition

In Phase 1, retrieval should assume a **strict D&D 3.5e corpus boundary**.

The Phase 1 implementation is lexical-first and domain-aware. The concrete pipeline is:

1. **Normalize** the raw query — case folding, punctuation cleanup, term alias expansion, protected phrases (`scripts/retrieval/query_normalization.py`).
2. **Lexical retrieve** from the FTS/BM25 index over the chunk corpus (`scripts/retrieval/lexical_index.py`).
3. **Hydrate match signals** — exact phrases, protected phrases, section-path hit, token overlap (`scripts/retrieval/match_signals.py`).
4. **Composite score** — BM25 + match-signal boosts + chunk-type prior (rule-bearing types outrank illustrative ones).
5. **Constraint filtering** — edition, source type, authority level, and excluded-source hard filters applied before a candidate is admitted.
6. **Section-aware shaping** — group candidates by `(document_id, section_root)` and sort groups by best rank within group (`scripts/retrieval/candidate_shaping.py`).
7. **Evidence pack** — package the shaped output with the normalized query, constraints summary, per-item evidence (content, chunk type, source ref, locator, match signals, section root), and a pipeline trace for debugging (`scripts/retrieval/evidence_pack.py`).

Semantic / vector retrieval is deferred to Phase 2 hybrid extension as described in `docs/chunking_retrieval_design.md`.

### 4.7 Answer composition

The answer composition layer turns retrieved evidence into a grounded response.

Its responsibilities include:

- answering the user question from retrieved evidence
- distinguishing direct support from supported inference
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

### Stage A - Raw source layer

Examples:

- PDF rulebooks
- text exports
- structured source text
- future errata documents

This layer is the original input and should remain distinct from downstream processed forms.

### Stage B - Canonical document layer

This layer contains normalized document objects derived from the raw sources.

A canonical document should preserve:

- source identity
- edition
- document structure
- source-native locator information when available
- cleaned content

### Stage C - Chunk layer

This layer contains stable evidence objects derived from canonical documents.

A chunk should preserve:

- chunk identity
- source reference
- parent canonical document identity
- locator
- chunk type
- chunk text

Chunk objects should remain stable evidence objects. Embeddings or engine-specific index fields belong in a derived index layer rather than in the chunk contract itself.

### Stage D - Index artifact layer

This layer contains derived retrieval artifacts keyed to chunk identities.

Examples include:

- embedding vectors
- ANN index metadata
- BM25 or hybrid retrieval artifacts
- engine-specific filter records

This layer should be cheap to regenerate when retrieval strategy changes.

### Stage E - Retrieval result layer

This layer contains the subset of chunks selected as evidence for a user query.

Retrieval results should be treated as **candidate evidence**, not yet as trusted final claims.

### Stage F - Answer layer

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

### 7.2 Retrieval unit aligns with citation unit by default

By default, the chunk should function as both:

- a retrieval unit
- the default citation anchor

This keeps provenance stable and reduces ambiguity at answer time.

However, this is a design default rather than a hard invariant. A retrieved chunk may later yield multiple finer citation locators, and multiple chunks may jointly support a single answer segment.

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
- thin-slice validation before hard infrastructure choices

These assumptions reduce complexity and help prevent premature generalization.

## 9. Phase 0 sequencing

Phase 0 should validate one thin vertical slice before it locks infrastructure-heavy decisions.

That means:

- choose one real admitted source slice, such as SRD content or one PHB chapter
- build a small gold question set against that slice
- keep schemas thin and provisional until they survive real ingestion, chunking, and citation examples

Choosing a final vector service, final model set, or fully expanded schema too early increases contract drift risk.

## 10. Excluded architecture concerns for Phase 1

The following concerns are intentionally deferred:

- public multi-user system design
- authentication and tenancy
- live sync across multiple users
- production deployment topology
- scaling architecture
- plugin ecosystem or third-party extensions
- generalized support for many game systems

## 11. Key architectural boundaries

### Boundary A - Source boundary
Only intentionally selected D&D 3.5e corpus sources are considered in-scope.

### Boundary B - Canonical boundary
Raw documents and canonical documents are different objects and must not be conflated.

### Boundary C - Chunk boundary
Chunking is downstream from canonical normalization and may evolve independently.

### Boundary D - Index boundary
Index artifacts are derived from chunks and may be regenerated without rewriting the chunk corpus.

### Boundary E - Evidence boundary
Retrieved chunks are the evidence set available to the answer layer.

### Boundary F - Citation boundary
User-visible citations must resolve to preserved provenance rather than freeform model output.

## 12. Future extension points

The architecture should leave room for future additions without forcing them into Phase 1.

Potential extension points include:

- errata and FAQ overlays
- reranking
- comparison mode across rulesets or editions
- support for structured table-aware retrieval
- source priority policies
- quote extraction policies

These should be added intentionally rather than assumed by default.

## 13. Open design questions

The following questions remain open after the thin vertical slice is validated:

- Which additional chunk types are worth adding beyond the initial slice?
- When should citation locators split finer than chunk locators?
- How should conflicts between primary text and later errata be represented?
- What evaluation threshold is strong enough to justify corpus expansion?
- Which local index and model choices are good enough for the first implementation?

## 14. Summary

In one sentence:

> The architecture is a staged, provenance-preserving RAG pipeline that turns curated D&D 3.5e source material into grounded answers with traceable citations.
