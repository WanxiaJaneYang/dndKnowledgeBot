# Metadata Contract

> **English** | [中文](zh/metadata_contract.md)

## Goal

Define one shared metadata vocabulary for source identity and locator semantics so source configs, schemas, and examples compose without field translation.

## Shared Vocabulary

### Core fields

- `source_id`
  Stable snake_case source identifier such as `srd_35` or `phb_35`.
- `edition`
  Edition label. Use `3.5e` for Phase 1.
- `source_type`
  Source category enum:
  - `core_rulebook`
  - `supplement_rulebook`
  - `errata_document`
  - `faq_document`
  - `srd`
  - `curated_commentary`
  - `personal_note`
- `authority_level`
  Source authority enum:
  - `official`
  - `official_reference`
  - `curated_secondary`
  - `personal_note`

### Locator semantics

- `locator`
  Evidence-level location object attached to canonical documents, chunks, and citations.
- `locator_policy`
  Source-level locator guidance stored in source manifests and similar source-policy configs.

`locator_policy` and `locator` are intentionally separate:
- `locator_policy` defines how a source should be located.
- `locator` records the concrete location instance for a specific evidence object.

## Evidence Locator Shape

`locator` supports both paginated and non-paginated sources.

Expected fields (when available):
- `page_range`
- `section_path`
- `entry_id`
- `entry_title`
- `source_location`

At least one of those must be present.

## Examples

### Non-paginated source example (`srd_35`)

```json
{
  "source_ref": {
    "source_id": "srd_35",
    "title": "System Reference Document",
    "edition": "3.5e",
    "source_type": "srd",
    "authority_level": "official_reference"
  },
  "locator": {
    "section_path": ["Classes", "Fighter", "Class Features", "Bonus Feats"],
    "entry_title": "Bonus Feats",
    "source_location": "ClassesI.rtf > Bonus Feats"
  }
}
```

### Paginated source example (`phb_35`)

```json
{
  "source_ref": {
    "source_id": "phb_35",
    "title": "Player's Handbook",
    "edition": "3.5e",
    "source_type": "core_rulebook",
    "authority_level": "official"
  },
  "locator": {
    "section_path": ["Chapter 3: Classes", "Fighter", "Class Features", "Bonus Feats"],
    "entry_title": "Bonus Feats",
    "page_range": {
      "start": 37,
      "end": 38
    }
  }
}
```

## Chunk Adjacency Fields

`schemas/chunk.schema.json` sets `additionalProperties: false` and declares the following adjacency fields as optional string properties (not in `required`):

- `parent_chunk_id` — parent chunk identifier when the chunk belongs to a larger entry or table.
- `previous_chunk_id` — previous adjacent chunk identifier.
- `next_chunk_id` — next adjacent chunk identifier.

These are known, schema-defined fields — producers may omit them, but must not emit other custom adjacency fields under different names. Absence means the chunk is a boundary chunk (first or last in its section, or a top-level chunk with no parent).

Adjacency fields support downstream reasoning that needs chunk context beyond a single retrieval hit — for example, consolidating adjacent chunks that jointly describe one rule, or surfacing a parent section when a spell entry is retrieved alone. They are also mirrored into the lexical retrieval index (see `scripts/retrieval/lexical_index.py`) so retrieval can read them without a separate chunk-object lookup.

### Parent vs Child Adjacency Semantics

`previous_chunk_id` and `next_chunk_id` carry two distinct kinds of adjacency that share the same wire format but mean different things:

- **Child sibling adjacency** (children of the same parent): genuine content continuity. A later paragraph follows an earlier one within the same entry. Retrieval can use sibling adjacency for context expansion.
- **Parent file-order adjacency** (parent chunks within the same source file): convenience link only — does NOT imply semantic continuity. Adjacent spell parents (e.g., Sanctuary → Scare → Scorching Ray) happen to share a source file; they are independent entries with no shared narrative.

Retrieval and evidence-pack assembly must:

- Use `parent_chunk_id` (children → parent) as the consolidation axis when a child matches.
- NOT treat parent file-order adjacency as semantic context.
- Children of one parent do NOT link to children of an adjacent parent.

The `split_origin` field on child chunks (`structure_cut` | `paragraph_group`) records which split mechanism produced each child — diagnostic only, not used for routing.

## Source Ref and Locator in Answer Segments

`source_ref` and `locator` are defined once in `schemas/common.schema.json` and reused verbatim across canonical documents, chunks, and citations. This is the provenance chain that flows from ingestion to the final answer:

1. Ingestion attaches a `source_ref` and `locator` to each canonical document.
2. The chunker propagates them (possibly narrowing the `locator`) onto every emitted chunk.
3. The retrieval layer preserves both fields on each evidence item (see `scripts/retrieval/evidence_pack.py::EvidenceItem`).
4. The answer layer copies them into the `citations[]` entries of `schemas/answer_with_citations.schema.json`, each of which is a reusable object with `citation_id`, `chunk_id`, `source_ref`, `locator`, and `excerpt`.
5. `answer_segments[].citation_ids` then reference those citation objects by id, binding claim text to preserved provenance.

Because `source_ref` and `locator` keep the same shape end-to-end, answer rendering can resolve a cited segment back to the source without field translation. Narrowing within a chunk (e.g. a specific paragraph) lives in the citation-level `locator` and `excerpt`, not in a duplicate chunk record — see `docs/citation_policy.md` §5.

## Contract Application

This contract is the normalization target for:

- `configs/source_registry.yaml`
- `configs/bootstrap_sources/srd_35.manifest.json`
- `schemas/common.schema.json`
- `examples/canonical_document.example.json`
- `examples/chunk.example.json`
- `examples/answer_with_citations.example.json`

If future schema updates conflict with this document, this document should be updated first or in the same PR.
