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
- `phase1_gold.zh.yaml`
  - Chinese-language counterpart of `phase1_gold.yaml`.
  - Uses the same `eval_id`, `question_type`, and expected metadata contract.
  - Intended for Chinese-user-facing evaluation while preserving one-to-one case mapping.

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

## How to Rerun

```
python scripts/run_phase1_eval.py
```

Writes `evals/reports/phase1_gold_latest.json` (machine) and `_latest.md` (human). Failing cases first, clean tail collapsed. The harness is a reporter — exits 0 regardless of tag counts. See `docs/plans/2026-04-25-issue-24-gold-eval.md` for the design.
