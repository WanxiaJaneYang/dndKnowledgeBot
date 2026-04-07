# Product Scope

## Goal

Define the boundaries of Phase 1 of the D&D 3.5 Knowledge Chatbot.

## Scope

**In scope:**
- D&D 3.5 Edition only
- Official primary sources: Player's Handbook (PHB), Dungeon Master's Guide (DMG), Monster Manual (MM)
- Official supplemental sources: System Reference Document (SRD), official errata, official FAQ
- Natural language rule queries with cited answers
- Explicit abstention when evidence is insufficient or ambiguous

**Out of scope (Phase 1):**
- Other D&D editions (3.0, 4e, 5e, etc.)
- Third-party supplements, Pathfinder, or other compatible systems
- Homebrew content (architecture supports it; Phase 1 excludes it)
- Public-facing hosting or multi-user access
- Character sheet management, dice rolling, or campaign tracking
- Real-time web retrieval or wiki lookups

## Non-Goals

- Replacing a GM or serving as a rules arbiter
- Reproducing full rulebook text verbatim in outputs
- Supporting redistribution of copyrighted corpus content

## Key Constraints

- Private local use only
- Lawfully obtained source materials assumed
- Official sources take precedence over all unofficial content
- System must clearly indicate when an answer is based on unofficial or low-authority sources

## Open Questions

- Which official supplements beyond PHB/DMG/MM are in scope for Phase 1? (e.g., Complete series, Spell Compendium)
- Is the SRD treated as equivalent authority to the PHB, or lower?
- What is the minimum acceptable citation granularity? (page-level vs. section-level)
