# Hierarchical Chunking for Entry-Like Documents

**Date**: 2026-04-21
**Issue**: #60
**Status**: Design

## 1. Goal

Make the canonical corpus and chunk corpus granular enough for precise
retrieval and citation of individual entries (spells, feats, skills,
conditions, etc.), and support parent-child chunk relationships for
entries large enough to benefit from sub-splitting.

## 2. Scope and non-goals

### In scope

- **Phase A**: Entry-aware canonical docs — ingestion produces one
  canonical doc per entry for spell, feat, skill, and condition content.
- **Phase B**: Hierarchical chunking — the chunker produces parent +
  child chunks for entries exceeding a size threshold.
- Coverage: `spell_entry`, `feat_entry`, `skill_entry`,
  `condition_entry`. Other entry types (`class_feature`,
  `glossary_entry`) can follow the same pattern later.

### Non-goals

- Whole-table / row-level chunking strategy.
- Non-entry long-section generic paragraph splitter.
- Retrieval ranking or reranking logic changes.
- Answer composer / citation renderer changes.
- Changes to the RTF decoder, IR builder, sectioning, or boundary filter
  modules.

## 3. Current state and problem

The ingestion pipeline detects section boundaries by heading heuristics.
Source files that contain many entries under a single heading (e.g.,
`SpellsS.rtf` with ~36 spells) produce a single canonical doc. The
chunker's v1-section-passthrough maps 1 canonical doc → 1 chunk.

Result:

| File | Canonical docs | Chunk size |
|------|---------------|------------|
| SpellsS.rtf | 1 | 96,958 chars |
| SpellsP-R.rtf | 1 | 77,190 chars |
| SpellsA-B.rtf | 1 | 57,887 chars |
| TypesSubtypesAbilities.rtf | 2 | 79,974 chars (largest) |
| AbilitiesandConditions.rtf | 41 | 15,134 chars (CONDITIONS block) |

60 chunks exceed 8K chars. 9 spell-file chunks exceed 27K chars. These
are unusable for retrieval — embeddings are meaningless, lexical matches
return entire files, and citations cannot point to specific entries.

## 4. Architecture: Option C (A → B)

Target architecture is two-layer:

- **Ingestion layer (Phase A)**: Entry identity is source of truth.
  Canonical docs represent stable logical units that can later be
  re-chunked.
- **Chunker layer (Phase B)**: Retrieval fragments with parent-child
  relationships. Parent = full entry, children = paragraph groups / stat
  blocks / table fragments.

Delivery order: A first (fix source truth granularity), then B (add
retrieval fragment granularity).

Why not chunker-only (Option B):

1. Canonical corpus stays coarse, violating its design purpose as
   "stable logical unit that can be re-chunked."
2. Locator / citation anchors remain file-level — chunker cleverness
   cannot fix coarse source anchors.
3. Chunker takes on dual responsibility: identifying source-native
   logical units AND generating retrieval fragments.

---

## 5. Phase A: Entry-aware ingestion

### 5.1 Insertion point

Entry detection runs **after** boundary filtering, **before** canonical
doc emission. This is additive — no changes to existing pipeline stages.

```
RTF → decode → IR → section split → boundary filter
    → [NEW] expand_entries → emit canonical docs
```

### 5.2 New module: `scripts/ingest_srd35/entry_splitter.py`

Public API:

```python
def expand_entries(
    sections: list[dict],
    file_stem: str,
) -> list[dict]:
    """Expand entry-like sections into per-entry sub-sections.

    Tries detectors in priority order. First match wins.
    Non-entry sections pass through unchanged.
    """
```

Data types:

```python
@dataclass
class EntrySpan:
    title: str       # "Sanctuary"
    slug: str        # "sanctuary"
    start: int       # char offset in section content
    end: int         # char offset (exclusive)
```

Detector registry (tried in order):

```python
_DETECTORS = [
    detect_spell_entries,
    detect_feat_entries,
    detect_skill_entries,
    detect_condition_entries,
]
```

Each detector signature:

```python
def detect_spell_entries(content: str) -> list[EntrySpan] | None
```

Returns `None` if content does not match this type (detector does not
apply). Returns a list of `EntrySpan` if entries are detected. Content
before the first entry and between entries (gaps) becomes preamble
sections. A detector should return `None` rather than a single-entry
list that spans the whole section — that would be a no-op expansion.

### 5.3 Detection patterns

**Spells**: Two-line pattern — a name line (short, title-cased) followed
by a school line matching one of the 8 schools (Abjuration, Conjuration,
Divination, Enchantment, Evocation, Illusion, Necromancy, Transmutation),
with optional subschool in parentheses. This is unambiguous across the
SRD.

**Feats**: Name line matching `ALL CAPS NAME [TAG]` where TAG is one of
GENERAL, FIGHTER, METAMAGIC, ITEM CREATION, EPIC, DIVINE, PSIONIC, etc.

**Skills**: Name line matching `ALL CAPS NAME (ABILITY)` where ABILITY
is STR, DEX, CON, INT, WIS, CHA.

**Conditions**: Within the CONDITIONS section specifically (detected by
parent section title), each condition starts with a single title-cased
word or short phrase on its own line, followed by a description
paragraph.

### 5.4 Canonical doc output shape

Before (mega-doc):

```json
{
  "document_id": "srd_35::spellss::001_spellss",
  "document_title": "SpellsS",
  "locator": {
    "section_path": ["SpellsS", "SpellsS"],
    "source_location": "SpellsS.rtf#001_spellss"
  },
  "content": "<97K chars>"
}
```

After (per-entry doc):

```json
{
  "document_id": "srd_35::spellss::001_sanctuary",
  "document_title": "Sanctuary",
  "locator": {
    "section_path": ["Spells S", "Sanctuary"],
    "entry_title": "Sanctuary",
    "source_location": "SpellsS.rtf#001_sanctuary"
  },
  "content": "Sanctuary\nAbjuration\nLevel: Clr 1, Protection 1\n..."
}
```

Key field rules:

- **`document_id`**: `{source_id}::{file_slug}::{index}_{entry_slug}`.
  Sequential index preserves source order.
- **`document_title`**: The entry name.
- **`section_path[0]`**: Human-readable file label (e.g., `"Spells S"`
  not `"SpellsS"`). Uses `parent_section_title` from expanded entry.
- **`section_path[1]`**: Entry title.
- **`entry_title`**: Populated in locator. Already defined in
  `common.schema.json` — no schema change needed.
- **`source_location`**: `{file}.rtf#{index}_{entry_slug}`.

### 5.5 Preamble handling

Content before the first detected entry in a section (typically the OGL
one-liner or an intro paragraph) becomes its own canonical doc with:

- The original section-level identity (no `entry_title`)
- `section_path`: `[file_label, section_title]` (existing behavior)
- Index `001` in the file, with entries starting from `002`

### 5.6 Pipeline changes

In `pipeline.py`, one insertion after boundary filtering:

```python
sections, boundary_decisions = apply_boundary_filters(...)
sections = expand_entries(sections, file_slug)  # NEW
```

The canonical doc emission loop gains one conditional — if a section dict
contains `entry_title`, propagate it into the locator and use
`parent_section_title` for `section_path[0]`.

### 5.7 Reporting

The existing `canonical_report.json` gains an optional
`"entry_expansion"` summary:

```json
{
  "entry_expansion": {
    "sections_expanded": 9,
    "entries_produced": 723,
    "by_type": {
      "spell": {"sections": 9, "entries": 687},
      "feat": {"sections": 0, "entries": 0},
      "skill": {"sections": 0, "entries": 0},
      "condition": {"sections": 0, "entries": 0}
    }
  }
}
```

### 5.8 Schema impact

None. All fields used (`entry_title`, `section_path`, `source_location`)
are already defined in `common.schema.json` and
`canonical_document.schema.json`.

---

## 6. Phase B: Hierarchical chunking

### 6.1 When Phase B applies

After Phase A, most entry-level canonical docs will be small enough for
the 1:1 passthrough to work well. Phase B adds parent-child splitting
for entries that still exceed a configurable size threshold (e.g., 4K–6K
chars).

### 6.2 Multi-chunk output

Replace `_build_chunk` with `_build_chunks`:

```python
def _build_chunks(canonical_doc, ...) -> list[dict]:
    content_len = len(canonical_doc["content"])
    if content_len <= CHILD_THRESHOLD:
        return [_build_parent_chunk(canonical_doc, ...)]
    parent = _build_parent_chunk(canonical_doc, ...)
    children = _split_into_children(canonical_doc, parent["chunk_id"], ...)
    return [parent] + children
```

### 6.3 Parent chunk

- `chunk_id`: `chunk::{document_id}` (same as today)
- `chunk_type`: entry-specific type (spell_entry, feat_entry, etc.)
- `content`: full entry text
- No `parent_chunk_id`

### 6.4 Child chunks

- `chunk_id`: `chunk::{document_id}::child_{index:03d}`
- `chunk_type`: `paragraph_group` (default), or more specific if
  detectable
- `content`: a fragment of the parent's content
- `parent_chunk_id`: parent's `chunk_id`
- Sibling adjacency: `previous_chunk_id` / `next_chunk_id` among
  children only

### 6.5 Child splitting strategy

- Split at paragraph boundaries (double newline).
- Target child size: 1K–2K chars.
- Never split mid-paragraph.
- Keep stat block fields together where possible (detect stat block
  field patterns like `Level:`, `Components:`, `Casting Time:`).

### 6.6 Adjacency rules

- **File-level adjacency**: Between parent chunks only (same as today's
  chunk-to-chunk adjacency).
- **Sibling adjacency**: Between children of the same parent.
- Children do NOT link to children of adjacent parents.

### 6.7 Report changes

`chunk_report.json` records gain `parent_chunk_id` field. Summary stats
include parent count vs child count.

---

## 7. Testing strategy

### Phase A tests

**Unit tests** (`tests/test_entry_splitter.py`):

- Spell detection: 3 concatenated spells → 3 EntrySpan with correct
  titles/slugs/offsets.
- Spell edge cases: subschool `(Healing)`, `Greater`/`Lesser`/`Mass`
  prefix, variable whitespace between entries.
- Feat detection: `ALL CAPS [TAG]` → correct EntrySpan.
- Skill detection: `ALL CAPS (ABILITY)` → correct EntrySpan.
- Condition detection: within CONDITIONS section → per-condition entries.
- No-match passthrough: generic prose → `None`.
- Preamble handling: OGL header before first entry → preamble section.

**Integration tests** (in `tests/test_ingest_srd_35.py`):

- Synthetic RTF with 3 spell entries → 3 canonical docs with correct
  `document_id`, `section_path`, `entry_title`.
- Non-entry content → still one canonical doc (regression test).

**Golden tests**:

- Add spell-file excerpt fixture (2–3 spells).
- Update golden outputs for new per-entry canonical docs.
- Existing non-entry golden tests pass unchanged.

### Phase B tests

**Unit tests** (in `tests/test_chunker.py`):

- Small entry → parent only, no children.
- Large entry → parent + N children, `parent_chunk_id` correct.
- Child sibling adjacency correct.
- Parent has no `parent_chunk_id`.
- Child IDs stable and deterministic.

**Golden tests**:

- Update fixture corpus with at least one entry-like fixture.
- Golden chunk outputs reflect hierarchy.

---

## 8. Delivery plan

### PR 1: Entry splitter module + spell detector

- New `scripts/ingest_srd35/entry_splitter.py` with `expand_entries()`
  and `detect_spell_entries()`.
- Edit `pipeline.py`: insert `expand_entries()` call + `entry_title`
  propagation.
- Unit tests for spell entry detection.
- Integration test with synthetic multi-spell RTF.
- Fixture + golden test updates.
- Re-run on full corpus, verify spell files expand.

### PR 2: Feat + skill + condition detectors

- Add `detect_feat_entries()`, `detect_skill_entries()`,
  `detect_condition_entries()`.
- Unit tests for each detector.
- Golden test updates.
- Re-run on full corpus.

### PR 3: Chunker multi-chunk output (Phase B)

- Refactor `_build_chunk` → `_build_chunks`.
- Adjacency rules for parent vs child levels.
- `chunk_report.json` parent/child records.
- Unit tests for 1-to-many output, parent_chunk_id, sibling adjacency.
- Golden chunk output updates.

### PR 4: Hierarchical child splitting strategy

- `_split_into_children()` with paragraph-boundary splitting.
- Size threshold configuration.
- Stat block grouping heuristics.
- Tests for splitting logic and edge cases.

---

## 9. Risks and open questions

1. **Spell detection accuracy**: The name + school two-line pattern
   should be robust, but spells with unusual formatting (e.g., spells
   whose description starts on the same line as the school) need
   verification against the actual corpus.

2. **Feat/skill coverage**: Most feats and skills are already
   well-split by heading detection. The main value is for files where
   they aren't (e.g., the CONDITIONS block in AbilitiesandConditions.rtf).
   Need to audit which feat/skill files actually need entry splitting vs
   which are already correct.

3. **Numbering stability**: If the ingestion pipeline is re-run after
   source content changes, entry indices may shift. This is acceptable —
   `document_id` stability is already tied to source content stability.

4. **Downstream chunk regeneration**: After Phase A, the chunker must
   be re-run to produce right-sized chunks. The chunk corpus will change
   significantly (many more, smaller chunks). Any downstream consumers
   (retrieval index, tests) must be regenerated.

5. **Phase B threshold tuning**: The child splitting threshold (4K–6K
   chars) needs empirical tuning after Phase A lands. Most spell entries
   are 500–3000 chars and won't need children at all.

---

## 10. Alternatives considered

### A. Chunker-only splitting (Option B)

Entry detection and sub-splitting entirely in the chunker. Rejected
because it leaves the canonical corpus coarse, violates the "stable
logical unit" design principle, and mixes two responsibilities in one
layer.

### B. IR-level entry detection

Insert entry-type block classification into `build_extraction_ir`,
making the IR builder aware of entry boundaries. Rejected because it's
more invasive (changes two existing modules), and the boundary filter
would need new rules to avoid incorrectly merging entry boundaries.

### C. Regex-based splitting in a preprocessing step

A standalone script that splits mega canonical docs after the fact.
Rejected because it creates an out-of-pipeline artifact that doesn't
integrate with reporting, provenance tracking, or the test harness.
