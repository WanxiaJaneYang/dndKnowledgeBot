# PR Evidence Standard

> **English** | [中文](../zh/standards/pr_evidence.md)

Pipeline behavior changes must include inspectable evidence, not only "tests passed".

## Minimum Evidence By PR Type

| PR type | Required evidence |
|---|---|
| Ingestion change | Updated fixture preview (`tests/fixtures/PREVIEW.md`) and/or committed golden diff under `tests/fixtures/expected/` |
| Chunking change | Golden chunk diff + fixture preview section update |
| Retrieval change | Retrieval integration-test output (e.g. `tests/test_evidence_pack.py`, `tests/test_lexical_retriever.py`) plus an end-to-end example on the fixture corpus showing the evidence-pack handoff (normalized query, constraints summary, ranked evidence items, pipeline trace) |
| Metadata-schema change | Diff of the chunk-index structure (e.g. `chunk_metadata` columns in `scripts/retrieval/lexical_index.py`) alongside the JSON schema diff, updated golden outputs, and schema validation gate result |
| Schema change | Updated golden outputs + schema validation gate result |

## Fixture-Based Evidence Flow

1. Run: `python scripts/preview_fixtures.py --update-golden`
2. Commit:
   - `tests/fixtures/srd_35/*.rtf` (real SRD-derived fixture files)
   - `tests/fixtures/srd_35/FIXTURE_SOURCE_MAP.json`
   - `tests/fixtures/PREVIEW.md`
   - `tests/fixtures/expected/extracted/*`
   - `tests/fixtures/expected/extracted_ir/*`
   - `tests/fixtures/expected/canonical/*`
3. Verify: `python -m unittest tests.test_golden_ingestion -v`

PRs that change pipeline behavior but do not update preview/golden evidence are considered incomplete.
