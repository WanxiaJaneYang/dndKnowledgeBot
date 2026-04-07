# Corpus Ingestion Design

## Goal

Define how raw source files are converted into normalized, source-traceable canonical documents.

## Scope

- Covers: extraction and normalization stages only
- Does not cover: chunking (see chunking_retrieval_design.md), indexing, or retrieval

## Proposed Design

### Stage 1 — Extraction

Convert raw source files (PDF) into per-page or per-section raw text with positional metadata preserved.

Outputs per page/section:
- raw text content
- page number(s)
- source file reference

**Open:** extraction library to use (candidates: pdfplumber, pymupdf, marker).

### Stage 2 — Normalization

Transform extracted text into canonical documents conforming to `canonical_document.schema.json`.

Normalization tasks:
- Assign `source_id` from source registry (`configs/source_registry.yaml`)
- Resolve `source_type` and `authority_level` from registry
- Detect and tag `section_path` (chapter → section → subsection)
- Clean extraction artifacts (ligatures, hyphenation, header/footer noise)
- Record `version` or `checksum` of the source file

Each canonical document represents one logical section of a source, not one page. Pages are recorded in `page_range`.

### Source Registry

All sources must be registered before ingestion. See `configs/source_registry.yaml` for the registry format.

Ingestion must reject any source not present in the registry.

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Section granularity | Logical section, not page | Pages split rules mid-sentence; sections preserve semantic coherence |
| Source identity | Registry-assigned `source_id` | Decouples ingestion from file paths |
| Version tracking | File checksum | Detects if a source file changes between ingestion runs |

## Alternatives Considered

- **Page-level canonical documents**: Simpler extraction, but splits rules across boundaries and produces poor citation anchors.
- **Full-book canonical document**: Loses section-level provenance needed for citation anchors.

## Risks and Open Questions

- PDF extraction quality varies significantly by book scan quality.
- Section boundary detection may require per-book heuristics or manual overrides.
- How to handle tables and multi-column layouts (common in PHB/DMG)?
- What to do with errata that modify specific paragraphs of existing canonical documents?

## Next Steps

- Evaluate PDF extraction libraries on a sample PHB chapter
- Define section boundary detection strategy
- Draft per-source extraction profiles if needed
