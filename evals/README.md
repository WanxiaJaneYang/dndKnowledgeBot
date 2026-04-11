# Evaluation Sets

This directory stores hand-built evaluation datasets used for early regression checks.

## Current Set

- `phase1_gold.yaml`
  - Scope: Phase 1 admitted bootstrap source slice (`srd_35`) only.
  - Size: 30 cases.
  - Coverage:
    - direct lookup
    - exception lookup
    - named entry lookup
    - multi-chunk support
    - table-dependent lookup
    - insufficient evidence / out-of-scope (abstain)

## Case Contract

Each case in `phase1_gold.yaml` includes:

- `eval_id`
- `question`
- `question_type`
- `expected_source_ids`
- `expected_section_or_entry`
- `expected_behavior`
- `expected_answer_notes`

`expected_behavior` is one of:

- `direct_answer`
- `supported_inference`
- `narrow_answer`
- `abstain`

## How To Use

Use this set as the default regression slice whenever retrieval, chunking, answer composition, citation format, or abstain logic changes.

At minimum, a regression pass should check:

1. Retrieval includes evidence from the expected source and section/entry.
2. The answer behavior matches `expected_behavior`.
3. Citation anchors support the claim type implied by `expected_answer_notes`.

