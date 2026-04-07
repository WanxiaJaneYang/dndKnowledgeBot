# Citation Policy

## 1. Purpose

This document defines how citations should work in the D&D 3.5e Knowledge Chatbot.

In this project, citation is not a cosmetic output feature. It is the visible proof that an answer is grounded in retrieved source material.

## 2. Policy objective

The system should produce answers that allow the user to inspect:

- what source supported the answer
- where in the source the support came from
- whether a statement was directly supported or partly inferred

The citation policy exists to make grounded answering verifiable.

## 3. Core principle

### Citation is evidence, not decoration

A citation should not be added merely to make an answer look trustworthy.

A citation must point back to a concrete retrieved evidence unit whose provenance was preserved earlier in the pipeline.

This means citation quality is downstream of:

- source identity quality
- ingestion quality
- chunk design
- retrieval quality
- answer composition discipline

## 4. Citation scope in Phase 1

Phase 1 assumes:

- a private, personal project
- D&D 3.5e only
- a curated corpus
- source-grounded rules answers

The policy therefore prioritizes:

- provenance clarity
- edition clarity
- useful location references
- simple, readable citation rendering

## 5. Citation unit

The default citation unit in Phase 1 should be the **retrieved chunk**.

This means a chunk functions as the minimum evidence unit that an answer may cite.

A citation should therefore refer to a chunk whose metadata can be resolved into a human-meaningful source reference.

## 6. Required provenance fields

At minimum, a citable chunk should preserve enough information to render:

- source title
- edition
- page range or equivalent location
- section path or entry identity when available
- stable source or chunk reference

Examples of useful provenance fields include:

- `source_id`
- `source_title`
- `edition`
- `page_start`
- `page_end`
- `section_path`
- `entry_title`
- `chunk_id`

## 7. Citation rendering goal

The user-facing citation should be readable enough that a human can inspect the supporting location without seeing raw internal IDs.

A citation should ideally answer:

- which book or source?
- which part of that source?
- how specific is the location?

## 8. Preferred citation shape

Phase 1 should prefer compact, human-readable citations such as:

- `Player's Handbook (3.5e), p. 137`
- `Player's Handbook (3.5e), pp. 137–138`
- `Player's Handbook (3.5e), Combat > Attacks of Opportunity, p. 137`
- `Player's Handbook (3.5e), Feat: Combat Reflexes, p. 92`

The exact final display format can be refined later, but it should remain concise and source-first.

## 9. Answer-to-citation binding

Every substantive answer unit should have visible support.

In practice, this means:

- each answer paragraph should cite one or more retrieved chunks
- a single strong citation is acceptable when one chunk directly supports the statement
- multiple citations are preferable when the answer combines separate supporting points

A citation should attach to the claim it supports, not merely appear at the end of the whole answer without structure.

## 10. Direct support vs inference

The system should distinguish between:

### Direct support
The source text states the rule or conclusion explicitly.

### Supported inference
The answer is not stated verbatim but follows from the retrieved evidence.

### Weak support
The citation is only loosely related and does not justify a confident claim.

The user should not be misled into thinking all cited statements are direct quotations of the rule text.

## 11. Signaling inference

When a claim is an inference rather than a direct textual statement, the answer should signal that clearly.

Examples of acceptable phrasing include:

- `This appears to imply ...`
- `Based on these passages ...`
- `The rule text does not say this directly, but it suggests ...`

The citation remains required even when the statement is inferential.

## 12. Insufficient evidence policy

If the system cannot find adequate support, it should not produce a citation-backed answer by force.

Instead, it should:

- abstain
- answer more narrowly
- identify the ambiguity
- say that the evidence currently retrieved is insufficient

Invented or weakly attached citations are worse than no citation.

## 13. Conflicting evidence policy

If retrieved evidence appears to conflict, the system should not hide the conflict.

Instead, the answer should prefer one of the following behaviors:

- present the conflict explicitly
- state that the current evidence is unresolved
- cite the competing locations separately

This is especially important if later phases introduce errata, FAQ, or layered source types.

## 14. Citation granularity

Phase 1 should aim for the best granularity reasonably preserved by ingestion and chunking.

Preferred order:

1. source + page + section or entry
2. source + page
3. source + section or entry
4. source only as a last resort

A citation that only names a book without a usable location is weak and should be treated as a degraded fallback.

## 15. Citation and quotation are not the same

A citation does not require a long verbatim quote.

For this project, the system should generally prefer:

- concise grounded summaries
- short supporting snippets where necessary
- location references that let the user inspect the original text

This is better than returning large blocks of source text by default.

## 16. Internal references vs user-facing citations

The system may use internal references such as chunk identifiers during answer composition.

However, those internal references should normally be translated into human-readable citations in the final response.

Example:

- internal: `C17`, `chunk_phb35_00017`
- user-facing: `Player's Handbook (3.5e), Combat > Attacks of Opportunity, p. 137`

## 17. Invalid citation behaviors

The system should treat the following as invalid behaviors:

- citing a source that was not retrieved
- citing a source that does not support the claim made
- attaching one citation to multiple unsupported claims
- using citations to imply certainty where the text is ambiguous
- collapsing conflicting evidence into a single unqualified citation
- dropping edition identity when it matters

## 18. Citation quality bar

A good Phase 1 citation should satisfy most of the following:

- points to the actual supporting source
- is specific enough for a human to inspect
- stays within the D&D 3.5e corpus boundary
- is attached to the correct claim
- does not overstate what the source proves

## 19. Future compatibility

The citation system should be designed so that later phases can support:

- source cards or expandable citation panels
- multiple evidence references per claim
- errata-aware or FAQ-aware citation layering
- structured provenance export for evaluation

Phase 1 does not need all of these features, but it should not block them.

## 20. Summary

In one sentence:

> A valid citation in this project is a human-readable rendering of a retrieved evidence unit whose provenance is strong enough to let the user verify the claim being made.
