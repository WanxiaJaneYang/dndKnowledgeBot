# SRD 3.5 Corpus Health Report

> **English** | [中文](zh/corpus_health_srd35.md) — Generated after Issue #27 full-pipeline run.

## Summary

| Metric | Value |
|---|---|
| Source files (RTF) | 86 |
| Canonical documents | 2 743 |
| Chunks | 2 743 |
| Ingestion errors | 0 |
| Pipeline | fetch → ingest → chunk (v1-section-passthrough) |

All 86 RTF files ingested without errors.

## Chunk Type Distribution

| Type | Count | % |
|---|---|---|
| `subsection` | 2 639 | 96.2 % |
| `generic` | 64 | 2.3 % |
| `rule_section` | 40 | 1.5 % |

The near-uniform `subsection` dominance is expected for Phase 1: the type classifier only promotes a doc to `rule_section` when the leaf section-path token exactly matches the root token (e.g. `['Races', 'Races']`). Most chapter content falls under distinct subsection headings and is correctly classified as `subsection`. Fine-grained types (`spell_entry`, `feat_entry`, etc.) require Phase 2 entry-level splitting.

## Content Length Distribution (characters)

| Percentile | Chars |
|---|---|
| min | 60 |
| p25 | 335 |
| median | 846 |
| p75 | 1 948 |
| p90 | 3 362 |
| p99 | 14 832 |
| max | 96 958 |

Median chunk is ~850 chars (~170 tokens). The distribution is right-skewed due to dense structured sections (spell lists, magic item catalogues) that cannot be split without Phase 2 entry-level parsing.

## Boundary Filter Fixes (this PR)

Initial run (before fixes) produced **4 006 chunks** with two categories of false splits:

### 1. Spell / power stat-block field lines (1 107 false splits eliminated)

RTF spell entries format their stat fields (Components, Range, Duration, Level, etc.) with bold text, which the section detector treated as section headings. This fragmented each spell across ~8 micro-chunks with section titles like `"Components: V, S"` or `"Spell Resistance: Yes"`.

**Affected files (17):** `SpellsA-B`, `SpellsC`, `SpellsD-E`, `SpellsF-G`, `SpellsH-L`, `SpellsM-O`, `SpellsP-R`, `SpellsS`, `SpellsT-Z`, `EpicSpells`, `DivineDomainsandSpells`, `PsionicSpells`, `PsionicPowersA-C`, `PsionicPowersD-F`, `PsionicPowersG-P`, `PsionicPowersQ-W`, `EpicMonsters(G-W)`.

**Fix:** `_looks_spell_block_field()` added to `boundary_filter.py`. Stat-block field lines are merged backward into the preceding section. Zero remaining after fix.

### 2. Named `Table:` headings accepted as sections (6 files)

Tables titled `Table: Epic Leadership`, `Table: Armor and Shields`, etc. were accepted as independent sections rather than merged with their parent. The existing merge logic only caught table-row syntax (titles containing `|`).

**Affected files:** `DivineAbilitiesandFeats`, `EpicFeats`, `EpicLevelBasics`, `EpicMagicItems1`, `EpicMagicItems2`, `EpicSpells`.

**Fix:** `_looks_table_label_title()` extended to also match `Table:` prefixed titles. Zero remaining after fix.

**Net result: 4 006 → 2 743 chunks (−1 263 false splits collapsed).**

## Known Remaining Issues

### Phase 2 — Entry-level aggregation (large chunks)

21 chunks exceed 20 000 chars. These are sections that aggregate many individual entries (spells, magic items, creature types) into a single canonical document because the Phase 1 section-passthrough strategy stops at the RTF section-heading level:

| Chars | Section |
|---|---|
| 96 958 | `SpellsS` / SpellsS intro (all S-level spells) |
| 79 974 | `TypesSubtypesAbilities` / TYPES, SUBTYPES, & SPECIAL ABILITIES |
| 77 190 | `SpellsP-R` / SpellsP-R intro |
| 71 154 | `MagicItemsV` / Wondrous Item Descriptions |
| … | (17 others in spell/magic-item chapters) |

These are expected limitations of v1-section-passthrough. Resolution requires Phase 2 entry-level splitting in the ingestion stage (recognize individual spell entries, magic item entries, etc. as canonical document boundaries).

Most embedding models support up to 8 000+ tokens (~40 000 chars), so none of these will be truncated at the embedding stage, but retrieval precision will be poor for queries targeting a specific spell or item within these blobs.

### Known false split — `MagicItemsV` / `Opal: Daylight` (46 320 chars)

The Helm of Brilliance description in `MagicItemsV.rtf` formats its gem-spell sub-entries with bold headings (e.g. `Opal: Daylight`). The boundary detector promoted one of these as a section boundary, splitting the wondrous items list into an incoherent chunk starting mid-Helm of Brilliance. The content of this chunk is valid wondrous item text but under a wrong section title.

This is a single-file issue. Resolution requires the boundary filter to understand that `ItemType: SpellName` formatted bold text inside an item description is not a section boundary — a deeper change than the current fix scope.

### Spell chapter intro blobs

After collapsing stat-block field splits, spell name headings themselves no longer form section boundaries because their direct body content is too small (typically just the school descriptor, e.g. "Conjuration [Creation]") before the next bold line appears. The spell entries collapse into a single large intro section per file.

This is a known limitation of Phase 1: entry-level spell splitting requires recognising spell-name headings even when the text between the heading and the next bold line is very short. Tracked as Phase 2 work.

## What This Means for the Next Step

The corpus is clean enough to proceed with the vector index:

- No ingestion errors
- No remaining stat-block field false splits
- Median chunk (~850 chars) is well within embedding model context windows
- Large aggregated chunks are a retrieval precision issue, not a correctness issue — queries will still find the right file/section, just with less granularity than a fully entry-split corpus

Phase 2 entry-level splitting should be scheduled before the first evaluation run that targets individual spells or magic items by name.
