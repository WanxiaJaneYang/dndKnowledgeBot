# Metadata Contract

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

## Contract Application

This contract is the normalization target for:

- `configs/source_registry.yaml`
- `configs/bootstrap_sources/srd_35.manifest.json`
- `schemas/common.schema.json`
- `examples/canonical_document.example.json`
- `examples/chunk.example.json`
- `examples/answer_with_citations.example.json`

If future schema updates conflict with this document, this document should be updated first or in the same PR.
