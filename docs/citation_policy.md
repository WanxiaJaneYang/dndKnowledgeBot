# Citation Policy

## Goal

Define how citations are attached to answers and rendered to the user.

## Scope

- Covers: citation anchor structure, citation granularity, rendering format, abstention behavior
- Does not cover: chunking (see chunking_retrieval_design.md), answer model prompting (see model_strategy.md)

## Citation Anchor

Every chunk carries a `citation_anchor` with the following required fields:

| Field | Description |
|---|---|
| `title` | Full book title (e.g., "Player's Handbook") |
| `edition` | Edition string (e.g., "3.5") |
| `page_range` | `{ "start": int, "end": int }` |
| `section_path` | Array of section headings from root to leaf |
| `authority_level` | Integer indicating source authority |
| `source_type` | Source category (e.g., `official_rulebook`) |

A citation anchor must be sufficient to locate the source passage without the system — a user must be able to open the book and find the cited page and section.

## Citation Granularity

**Required:** claim-level or paragraph-level citations — not only a trailing source list.

Each distinct rule claim in an answer must be individually cited. If two claims come from different sources, they carry different citations.

Example of preferred format:
> Fighters gain a bonus feat at 1st level and every even level thereafter [PHB p.37, §Fighter Class Features]. These bonus feats must be drawn from the Fighter Bonus Feat list [PHB p.38].

Example of what to avoid:
> Fighters gain bonus feats at even levels. *Sources: PHB.*

## Abstention Policy

The system must abstain rather than speculate when:
- No retrieved chunk meets the minimum relevance threshold
- The query concerns a rule not covered by any registered source
- The query concerns a different edition (unless comparison is explicitly requested)
- Conflicting rules exist and cannot be reconciled with available evidence

Abstention response must:
- State clearly that the answer cannot be found in the available sources
- Indicate which sources were searched
- Not fabricate page numbers, rule text, or source coverage

## Authority Conflict Handling

When retrieved chunks conflict (e.g., PHB text vs. errata):
- Prefer the source with the lower authority_level integer (higher authority)
- Surface the conflict explicitly to the user
- Cite both sources

## Risks and Open Questions

- How to render inline citations in the chosen interface (CLI, Discord, web)?
- What is the maximum number of citations per answer before it becomes unreadable?
- How to handle rules that require synthesizing 3+ chunks from different sections?
