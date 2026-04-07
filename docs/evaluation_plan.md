# Evaluation Plan

## 1. Purpose

This document defines how the D&D 3.5e Knowledge Chatbot should be evaluated.

The goal is not to create a perfect benchmark suite immediately. The goal is to make sure the project can answer a simple question clearly:

> is the system actually producing grounded, useful, citation-backed rules answers?

## 2. Why evaluation must exist early

RAG systems often appear convincing before they are reliable.

Without evaluation, it is easy to mistake the following for success:

- fluent answers
- plausible rules language
- citations that look correct but do not support the claim
- retrieval that feels relevant but misses the actual rule

This project needs evaluation early because groundedness and citation quality are its main product promises.

## 3. Phase 1 evaluation goals

Phase 1 evaluation should focus on the smallest set of checks that can reveal whether the system is behaving correctly.

The evaluation should test:

- retrieval relevance
- answer correctness relative to retrieved evidence
- citation faithfulness
- abstain behavior
- edition-boundary discipline

## 4. Evaluation principles

The evaluation approach should follow these principles:

### 4.1 Task-specific over generic
The system should be evaluated on D&D 3.5e rules tasks, not only on general QA impressions.

### 4.2 Evidence-aware over style-aware
A grounded but plain answer should score better than a stylish unsupported answer.

### 4.3 Small and inspectable first
A small manually inspectable dataset is more useful early than a large noisy benchmark.

### 4.4 Failure visibility matters
The evaluation should help expose failure modes, not merely assign a single score.

## 5. Core evaluation questions

The Phase 1 system should be tested against questions such as:

- Did retrieval surface the right rule or entry?
- Did the answer stay within the D&D 3.5e boundary?
- Did the answer overstate what the evidence supported?
- Did the citation actually support the claim?
- Did the system abstain when evidence was weak?

## 6. Evaluation dimensions

### 6.1 Retrieval relevance
Measures whether the retrieved evidence contains the material actually needed to answer the question.

### 6.2 Answer groundedness
Measures whether the answer follows from the retrieved evidence rather than unsupported model memory.

### 6.3 Citation faithfulness
Measures whether the cited source really supports the claim attached to it.

### 6.4 Answer usefulness
Measures whether the answer is actually responsive, understandable, and not overly vague.

### 6.5 Abstain correctness
Measures whether the system abstains when it should, and avoids abstaining when support is clearly available.

### 6.6 Scope discipline
Measures whether the answer stays within the admitted D&D 3.5e corpus rather than drifting into other editions or outside knowledge.

## 7. Suggested Phase 1 test categories

A small early evaluation set should include examples from several categories.

### 7.1 Direct rule lookup
Questions whose answer is likely found in one clearly defined rule section.

### 7.2 Exception lookup
Questions where the main rule has an exception or caveat.

### 7.3 Entry lookup
Questions about named feats, spells, skills, class features, or conditions.

### 7.4 Multi-chunk support
Questions where the answer requires combining more than one retrieved passage.

### 7.5 Ambiguous wording
Questions that are underspecified and may require narrow answering or clarification.

### 7.6 Table-dependent questions
Questions where the answer depends on a table or structured list.

### 7.7 Insufficient-evidence questions
Questions where the current corpus does not justify a clear answer.

## 8. Gold data philosophy

Phase 1 does not require a large formal benchmark.

Instead, it should begin with a small curated evaluation set where each item includes:

- the user question
- expected answer intent
- expected supporting source or section
- notes on acceptable inference
- notes on whether abstention is acceptable or required

This makes the evaluation dataset interpretable and maintainable.

## 9. Evaluation item structure

Each evaluation case should ideally record:

- `eval_id`
- `question`
- `question_type`
- `expected_source_ids`
- `expected_section_or_entry`
- `expected_answer_notes`
- `expected_behavior`

Possible values for `expected_behavior` may include:

- `direct_answer`
- `supported_inference`
- `narrow_answer`
- `abstain`

## 10. Manual evaluation first

Phase 1 should assume manual review is acceptable and useful.

A human evaluator should be able to inspect:

- the retrieved chunks
- the final answer
- the final citations
- whether the evidence actually supports the answer

This is more important early than building a complex automated scoring stack.

## 11. Early scoring rubric

A simple rubric is enough for Phase 1.

### Retrieval relevance
- `2` = clearly retrieved the necessary evidence
- `1` = partially relevant but incomplete
- `0` = failed to retrieve the needed evidence

### Answer groundedness
- `2` = answer is well supported by retrieved evidence
- `1` = partly supported, with some overreach or ambiguity
- `0` = unsupported or mostly hallucinated

### Citation faithfulness
- `2` = citation directly supports the claim
- `1` = citation is related but weak or incomplete
- `0` = citation does not support the claim

### Abstain correctness
- `2` = appropriate abstain or appropriate non-abstain
- `1` = borderline judgment
- `0` = clearly should have done the opposite

## 12. Failure analysis categories

When the system fails, the failure should be tagged rather than treated as a generic miss.

Useful early failure tags include:

- retrieval miss
- wrong edition or out-of-scope retrieval
- exception not captured
- table handling failure
- citation mismatch
- unsupported inference
- overconfident answer
- unnecessary abstain
- missing abstain

## 13. Minimal evaluation set size

A reasonable Phase 1 starting point is a small hand-built set, such as:

- 20 to 40 direct rule questions
- 10 to 20 exception-heavy questions
- 10 to 20 entry lookup questions
- a smaller number of table or abstain cases

The point is not the exact number. The point is to cover the main behavior categories with inspectable examples.

## 14. Evaluation checkpoints

The project should evaluate at several points, not only at the end.

Suggested checkpoints:

1. after initial chunking design is translated into data examples
2. after first retrieval prototype
3. after first answer-generation prototype
4. after citation rendering is added
5. after any major chunking or source-policy change

## 15. What Phase 1 should not optimize for yet

Phase 1 evaluation should not be dominated by:

- UI polish
- response style preference
- speed micro-optimizations
- broad fantasy or lore coverage
- multi-edition performance

These are secondary compared with grounded rules answering.

## 16. Success criteria

Phase 1 is in good shape when the system can consistently do most of the following on the early evaluation set:

- retrieve the correct rule material for common questions
- produce grounded answers from that material
- attach faithful citations
- avoid edition drift
- abstain when the evidence is insufficient

## 17. Summary

In one sentence:

> Phase 1 evaluation should be a small, inspectable, task-specific process that measures whether retrieval, answering, and citation actually work together as a grounded D&D 3.5e rules assistant.
