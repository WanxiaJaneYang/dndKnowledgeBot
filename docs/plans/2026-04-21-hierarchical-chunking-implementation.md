# Hierarchical Chunking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ingestion pipeline produce per-entry canonical docs for spells/feats/skills/conditions, then make the chunker produce parent-child chunks for large entries.

**Architecture:** New `entry_splitter.py` module inserted after boundary filtering in the ingestion pipeline. Each detector (spell, feat, skill, condition) returns `EntrySpan` objects that split mega-sections into per-entry sub-sections. Chunker then gains `_build_chunks` (1-to-many) with `parent_chunk_id` linking.

**Tech Stack:** Python 3, unittest, JSON schemas (no new dependencies)

**Spec:** `docs/plans/2026-04-21-hierarchical-chunking-design.md`

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `scripts/ingest_srd35/entry_splitter.py` | Entry detection and section expansion (spell, feat, skill, condition detectors) |
| `tests/test_entry_splitter.py` | Unit tests for all detectors and `expand_entries` |

### Modified files

| File | Change |
|------|--------|
| `scripts/ingest_srd35/pipeline.py` | Insert `expand_entries()` call + `entry_title`/`category` propagation to locator |
| `scripts/ingest_srd35/__init__.py` | Export `expand_entries` |
| `scripts/ingest_srd35/fixture_evidence.py` | No change needed (fixture RTFs don't contain spell/feat content) |
| `tests/test_ingest_srd_35.py` | Add integration test for entry expansion |
| `scripts/chunker/pipeline.py` | Refactor `_build_chunk` → `_build_chunks` for 1-to-many output |
| `tests/test_chunker.py` | Add parent-child hierarchy tests |

---

## PR 1: Entry Splitter Module + Spell Detector

### Task 1: Spell detector — unit tests and implementation

**Files:**
- Create: `scripts/ingest_srd35/entry_splitter.py`
- Create: `tests/test_entry_splitter.py`

- [ ] **Step 1: Write the EntrySpan dataclass and detect_spell_entries stub**

```python
# scripts/ingest_srd35/entry_splitter.py
"""Detect entry boundaries within ingested sections and expand them.

Inserted after boundary filtering, before canonical doc emission.
Each detector returns a list of EntrySpan or None if it doesn't apply.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .sectioning import sanitize_identifier

_SCHOOLS = {
    "Abjuration", "Conjuration", "Divination", "Enchantment",
    "Evocation", "Illusion", "Necromancy", "Transmutation", "Universal",
}
_SCHOOL_PATTERN = re.compile(
    r"^(" + "|".join(_SCHOOLS) + r")"
    r"(\s*\([^)]*\))?"       # optional subschool
    r"(\s*\[[^\]]*\])?$",    # optional descriptor
)


@dataclass
class EntrySpan:
    title: str
    slug: str
    start: int
    end: int
    category: str


def detect_spell_entries(content: str) -> list[EntrySpan] | None:
    """Detect spell entries by the Name + School two-line pattern.

    Returns None if fewer than 2 spells detected (not a spell list).
    """
    lines = content.split("\n")
    entry_starts: list[tuple[int, str]] = []  # (char_offset, title)

    char_offset = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (
            i + 1 < len(lines)
            and stripped
            and len(stripped) <= 80
            and _SCHOOL_PATTERN.match(lines[i + 1].strip())
        ):
            entry_starts.append((char_offset, stripped))
        char_offset += len(line) + 1  # +1 for the \n

    if len(entry_starts) < 2:
        return None

    spans: list[EntrySpan] = []
    for idx, (start, title) in enumerate(entry_starts):
        end = entry_starts[idx + 1][0] if idx + 1 < len(entry_starts) else len(content)
        spans.append(EntrySpan(
            title=title,
            slug=sanitize_identifier(title),
            start=start,
            end=end,
            category="Spells",
        ))
    return spans
```

- [ ] **Step 2: Write failing tests for spell detection**

```python
# tests/test_entry_splitter.py
from __future__ import annotations

import unittest

from scripts.ingest_srd35.entry_splitter import EntrySpan, detect_spell_entries


SAMPLE_SPELLS = (
    "Sanctuary\n"
    "Abjuration\n"
    "Level: Clr 1, Protection 1\n"
    "Components: V, S, DF\n"
    "Casting Time: 1 standard action\n"
    "\n"
    "Any opponent attempting to strike the warded creature must attempt a Will save.\n"
    "\n"
    "Scare\n"
    "Necromancy [Fear, Mind-Affecting]\n"
    "Level: Brd 2, Sor/Wiz 2\n"
    "Components: V, S, M\n"
    "\n"
    "This spell functions like cause fear, except it can affect one creature per three levels.\n"
    "\n"
    "Scorching Ray\n"
    "Evocation [Fire]\n"
    "Level: Sor/Wiz 2\n"
    "Components: V, S\n"
    "\n"
    "You blast your enemies with fiery rays.\n"
)


class DetectSpellEntriesTests(unittest.TestCase):
    def test_detects_three_spells(self) -> None:
        spans = detect_spell_entries(SAMPLE_SPELLS)
        self.assertIsNotNone(spans)
        self.assertEqual(len(spans), 3)
        self.assertEqual(spans[0].title, "Sanctuary")
        self.assertEqual(spans[1].title, "Scare")
        self.assertEqual(spans[2].title, "Scorching Ray")

    def test_spell_slugs(self) -> None:
        spans = detect_spell_entries(SAMPLE_SPELLS)
        self.assertEqual(spans[0].slug, "sanctuary")
        self.assertEqual(spans[1].slug, "scare")
        self.assertEqual(spans[2].slug, "scorching_ray")

    def test_category_is_spells(self) -> None:
        spans = detect_spell_entries(SAMPLE_SPELLS)
        for span in spans:
            self.assertEqual(span.category, "Spells")

    def test_spans_cover_full_content(self) -> None:
        spans = detect_spell_entries(SAMPLE_SPELLS)
        self.assertEqual(spans[0].start, 0)
        self.assertEqual(spans[-1].end, len(SAMPLE_SPELLS))
        for i in range(len(spans) - 1):
            self.assertEqual(spans[i].end, spans[i + 1].start)

    def test_span_content_correct(self) -> None:
        spans = detect_spell_entries(SAMPLE_SPELLS)
        first_content = SAMPLE_SPELLS[spans[0].start:spans[0].end]
        self.assertTrue(first_content.startswith("Sanctuary\n"))
        self.assertIn("Will save", first_content)
        self.assertNotIn("Scare", first_content)

    def test_subschool_detected(self) -> None:
        content = (
            "Cure Light Wounds\n"
            "Conjuration (Healing)\n"
            "Level: Clr 1\n"
            "\n"
            "Cures 1d8 damage +1/level.\n"
            "\n"
            "Cure Moderate Wounds\n"
            "Conjuration (Healing)\n"
            "Level: Clr 2\n"
            "\n"
            "Cures 2d8 damage +1/level.\n"
        )
        spans = detect_spell_entries(content)
        self.assertIsNotNone(spans)
        self.assertEqual(len(spans), 2)

    def test_single_spell_returns_none(self) -> None:
        content = (
            "Sanctuary\n"
            "Abjuration\n"
            "Level: Clr 1\n"
            "\n"
            "Any opponent attempting to strike must save.\n"
        )
        result = detect_spell_entries(content)
        self.assertIsNone(result)

    def test_non_spell_content_returns_none(self) -> None:
        content = (
            "DWARVES\n"
            "Dwarves are a stoic but stern race.\n"
            "They have darkvision 60 ft.\n"
        )
        result = detect_spell_entries(content)
        self.assertIsNone(result)

    def test_variable_whitespace_between_entries(self) -> None:
        content = (
            "Aid\n"
            "Enchantment (Compulsion) [Mind-Affecting]\n"
            "Level: Clr 2\n"
            "\n"
            "Aid grants a +1 morale bonus.\n"
            "\n"
            "\n"
            "Air Walk\n"
            "Transmutation [Air]\n"
            "Level: Clr 4\n"
            "\n"
            "The subject can walk on air.\n"
        )
        spans = detect_spell_entries(content)
        self.assertIsNotNone(spans)
        self.assertEqual(len(spans), 2)
        self.assertEqual(spans[0].title, "Aid")
        self.assertEqual(spans[1].title, "Air Walk")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `python -m pytest tests/test_entry_splitter.py -v`
Expected: All 9 tests PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/ingest_srd35/entry_splitter.py tests/test_entry_splitter.py
git commit -m "feat(ingestion): add spell entry detector with unit tests

Adds entry_splitter.py with detect_spell_entries() using the
Name + School two-line pattern. Returns EntrySpan list with title,
slug, offsets, and category='Spells'.

Part of #60 — Phase A entry-aware ingestion."
```

### Task 2: expand_entries and preamble handling

**Files:**
- Modify: `scripts/ingest_srd35/entry_splitter.py`
- Modify: `tests/test_entry_splitter.py`

- [ ] **Step 1: Add expand_entries function**

Append to `scripts/ingest_srd35/entry_splitter.py`:

```python
_DETECTORS = [
    detect_spell_entries,
]


def expand_entries(sections: list[dict], file_stem: str) -> list[dict]:
    """Expand entry-like sections into per-entry sub-sections.

    Tries detectors in priority order. First match wins per section.
    Non-entry sections pass through unchanged.
    """
    result: list[dict] = []
    for section in sections:
        content = section.get("content", "")
        spans: list[EntrySpan] | None = None
        for detector in _DETECTORS:
            spans = detector(content)
            if spans is not None:
                break

        if spans is None:
            result.append(section)
            continue

        # Handle preamble (content before first entry).
        if spans[0].start > 0:
            preamble_content = content[: spans[0].start].strip()
            if preamble_content:
                result.append({
                    **section,
                    "content": preamble_content,
                    "body_char_count": len(preamble_content),
                })

        # Emit one sub-section per entry.
        for span in spans:
            entry_content = content[span.start : span.end].strip()
            if not entry_content:
                continue
            result.append({
                **section,
                "section_title": span.title,
                "section_slug": span.slug,
                "content": entry_content,
                "body_char_count": len(entry_content),
                "entry_title": span.title,
                "parent_section_title": span.category,
            })

    return result
```

- [ ] **Step 2: Write tests for expand_entries**

Add to `tests/test_entry_splitter.py`:

```python
from scripts.ingest_srd35.entry_splitter import expand_entries


class ExpandEntriesTests(unittest.TestCase):
    def _make_section(self, content: str, title: str = "SpellsS") -> dict:
        return {
            "section_title": title,
            "section_slug": "spellss",
            "content": content,
            "body_char_count": len(content),
            "block_start_index": 0,
            "block_end_index": 0,
            "block_start_id": "b0001",
            "block_end_id": "b0001",
            "block_type_counts": {"paragraph": 1},
        }

    def test_expands_spell_section(self) -> None:
        section = self._make_section(SAMPLE_SPELLS)
        result = expand_entries([section], "spellss")
        # 3 spells, no preamble
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["section_title"], "Sanctuary")
        self.assertEqual(result[0]["entry_title"], "Sanctuary")
        self.assertEqual(result[0]["parent_section_title"], "Spells")

    def test_preamble_becomes_separate_section(self) -> None:
        content = (
            "This is OGL boilerplate.\n"
            "\n" + SAMPLE_SPELLS
        )
        section = self._make_section(content)
        result = expand_entries([section], "spellss")
        # 1 preamble + 3 spells
        self.assertEqual(len(result), 4)
        self.assertNotIn("entry_title", result[0])
        self.assertEqual(result[0]["content"], "This is OGL boilerplate.")
        self.assertEqual(result[1]["entry_title"], "Sanctuary")

    def test_non_entry_section_passes_through(self) -> None:
        section = self._make_section(
            "Dwarves are a stoic race.\nThey have darkvision.",
            title="DWARVES",
        )
        result = expand_entries([section], "races")
        self.assertEqual(len(result), 1)
        self.assertNotIn("entry_title", result[0])

    def test_preserves_non_entry_sections_in_mixed_list(self) -> None:
        spell_section = self._make_section(SAMPLE_SPELLS)
        plain_section = self._make_section("Just a paragraph.", title="Intro")
        result = expand_entries([plain_section, spell_section], "spellss")
        # 1 plain + 3 spells
        self.assertEqual(len(result), 4)
        self.assertNotIn("entry_title", result[0])
        self.assertEqual(result[1]["entry_title"], "Sanctuary")
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_entry_splitter.py -v`
Expected: All tests PASS (original 9 + new 4 = 13)

- [ ] **Step 4: Commit**

```bash
git add scripts/ingest_srd35/entry_splitter.py tests/test_entry_splitter.py
git commit -m "feat(ingestion): add expand_entries with preamble handling

expand_entries() tries detectors in priority order per section.
Preamble content before the first entry becomes its own section.
Non-entry sections pass through unchanged.

Part of #60 — Phase A entry-aware ingestion."
```

### Task 3: Integrate entry_splitter into the ingestion pipeline

**Files:**
- Modify: `scripts/ingest_srd35/pipeline.py:133-164`
- Modify: `scripts/ingest_srd35/__init__.py`

- [ ] **Step 1: Add import and call expand_entries in pipeline.py**

In `scripts/ingest_srd35/pipeline.py`, add import at line 8:

```python
from .entry_splitter import expand_entries
```

After line 134 (`sections, boundary_decisions = apply_boundary_filters(...)`), insert:

```python
        sections = expand_entries(sections, file_slug)
```

- [ ] **Step 2: Update the canonical doc emission loop to handle entry_title**

Replace lines 135-164 of `pipeline.py` (the `for index, section in enumerate(sections, start=1):` loop) with:

```python
        for index, section in enumerate(sections, start=1):
            section_slug = section["section_slug"]
            section_title = section["section_title"]
            source_location = f"{source_location_base}#{index:03d}_{section_slug}"

            # Entry-expanded sections carry entry_title and parent_section_title.
            entry_title = section.get("entry_title")
            if entry_title:
                section_path = [section["parent_section_title"], entry_title]
            else:
                section_path = [rtf_path.stem, section_title]

            document_id = f"{manifest['source_id']}::{file_slug}::{index:03d}_{section_slug}"

            locator: dict = {"section_path": section_path, "source_location": source_location}
            if entry_title:
                locator["entry_title"] = entry_title

            canonical_doc = {
                "document_id": document_id,
                "source_ref": source_ref,
                "locator": locator,
                "content": section["content"],
                "document_title": section_title,
                "source_checksum": raw_checksum,
                "ingested_at": ingested_at,
            }
            if canonical_docs is not None:
                canonical_docs.append(canonical_doc)

            canonical_path = canonical_root / f"{file_slug}__{index:03d}_{section_slug}.json"
            canonical_path.write_text(json.dumps(canonical_doc, indent=2) + "\n", encoding="utf-8")
            canonical_records.append(
                {
                    "document_id": document_id,
                    "canonical_path": str(canonical_path.relative_to(repo_root)),
                    "source_checksum": raw_checksum,
                    "section_path": section_path,
                    "source_location": source_location,
                }
            )
```

- [ ] **Step 3: Export expand_entries from __init__.py**

Add to `scripts/ingest_srd35/__init__.py`:

```python
from .entry_splitter import expand_entries
```

And add `"expand_entries"` to the `__all__` list.

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `python -m pytest tests/test_ingest_srd_35.py tests/test_golden_ingestion.py -v`
Expected: All existing tests PASS. The golden ingestion test still passes because the fixture RTFs (Description.rtf, DivineMinions.rtf, Legal.rtf, Races.rtf, SpecialMaterials.rtf) contain no spell entries, so `expand_entries` is a no-op.

- [ ] **Step 5: Commit**

```bash
git add scripts/ingest_srd35/pipeline.py scripts/ingest_srd35/__init__.py
git commit -m "feat(ingestion): integrate entry_splitter into pipeline

Calls expand_entries() after boundary filtering. Entry-expanded
sections get entry_title in locator and logical category as
section_path[0]. Non-entry sections unchanged.

Part of #60 — Phase A entry-aware ingestion."
```

### Task 4: Integration test — synthetic multi-spell RTF

**Files:**
- Modify: `tests/test_ingest_srd_35.py`

- [ ] **Step 1: Add integration test**

Add to `tests/test_ingest_srd_35.py` inside `IngestSrd35Tests`:

```python
    def test_spell_entries_expanded_into_per_entry_canonical_docs(self) -> None:
        spell_rtf = (
            "{\\rtf1\\ansi "
            "This material is Open Game Content.\\par\\par "
            "Sanctuary\\par Abjuration\\par "
            "Level: Clr 1, Protection 1\\par "
            "Components: V, S, DF\\par\\par "
            "Any opponent attempting to strike the warded creature must attempt a Will save.\\par\\par "
            "Scare\\par Necromancy [Fear, Mind-Affecting]\\par "
            "Level: Brd 2, Sor/Wiz 2\\par "
            "Components: V, S, M\\par\\par "
            "This spell functions like cause fear.\\par\\par "
            "Scorching Ray\\par Evocation [Fire]\\par "
            "Level: Sor/Wiz 2\\par "
            "Components: V, S\\par\\par "
            "You blast your enemies with fiery rays.\\par "
            "}"
        )
        (self.repo_root / "data/raw/srd_35/rtf/SpellsS.rtf").write_text(
            spell_rtf, encoding="latin-1",
        )
        result = ingest_source(self.manifest, self.repo_root, force=True)

        canonical_report = json.loads(Path(result["canonical_report"]).read_text(encoding="utf-8"))
        spell_records = [
            r for r in canonical_report["records"]
            if "spellss" in r["document_id"]
        ]

        # Expect: 1 preamble (OGL) + 3 spell entries = 4 docs from SpellsS
        # Plus the 2 original test RTFs (CombatI + AbilitiesandConditions)
        spell_entry_records = [r for r in spell_records if "Spells" in str(r.get("section_path", []))]
        spell_with_entry_title = [
            r for r in spell_records
            if r["section_path"][0] == "Spells"
        ]
        self.assertEqual(len(spell_with_entry_title), 3)

        # Verify section_path uses logical category
        for record in spell_with_entry_title:
            self.assertEqual(record["section_path"][0], "Spells")
            self.assertIn(record["section_path"][1], ["Sanctuary", "Scare", "Scorching Ray"])

        # Verify entry_title in canonical doc
        for record in spell_with_entry_title:
            canonical_path = self.repo_root / record["canonical_path"]
            doc = json.loads(canonical_path.read_text(encoding="utf-8"))
            self.assertEqual(doc["locator"]["entry_title"], doc["locator"]["section_path"][1])

    def test_non_spell_content_unaffected_by_entry_expansion(self) -> None:
        """Regression: files without entry patterns still produce one doc per section."""
        result = ingest_source(self.manifest, self.repo_root, force=True)
        # CombatI.rtf has 1 section, AbilitiesandConditions.rtf has 1 section
        self.assertEqual(result["documents_written"], 2)
```

- [ ] **Step 2: Run the integration test**

Run: `python -m pytest tests/test_ingest_srd_35.py::IngestSrd35Tests::test_spell_entries_expanded_into_per_entry_canonical_docs -v`
Expected: PASS

Run: `python -m pytest tests/test_ingest_srd_35.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_ingest_srd_35.py
git commit -m "test(ingestion): add integration test for spell entry expansion

Verifies synthetic multi-spell RTF produces per-entry canonical docs
with correct section_path=['Spells', name], entry_title, and preamble
handling. Also adds regression test for non-spell content.

Part of #60 — Phase A entry-aware ingestion."
```

### Task 5: Verify against real corpus and raise PR 1

**Files:** None modified (verification only)

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Push branch and open PR**

```bash
git push -u origin worktree-chunker-audit
```

Create PR with title: `feat(ingestion): entry-aware spell splitting (#60 PR 1/4)`

---

## PR 2: Feat + Skill + Condition Detectors

### Task 6: Feat detector

**Files:**
- Modify: `scripts/ingest_srd35/entry_splitter.py`
- Modify: `tests/test_entry_splitter.py`

- [ ] **Step 1: Write detect_feat_entries**

Add to `scripts/ingest_srd35/entry_splitter.py`:

```python
_FEAT_TAGS = {
    "GENERAL", "FIGHTER", "METAMAGIC", "ITEM CREATION", "EPIC",
    "DIVINE", "PSIONIC", "METAPSIONIC",
}
_FEAT_PATTERN = re.compile(
    r"^[A-Z][A-Z \-']+\[(" + "|".join(_FEAT_TAGS) + r")\]\s*$"
)


def detect_feat_entries(content: str) -> list[EntrySpan] | None:
    """Detect feat entries by ALL CAPS NAME [TAG] pattern.

    Returns None if fewer than 2 feats detected.
    """
    lines = content.split("\n")
    entry_starts: list[tuple[int, str]] = []

    char_offset = 0
    for line in lines:
        stripped = line.strip()
        if _FEAT_PATTERN.match(stripped):
            entry_starts.append((char_offset, stripped))
        char_offset += len(line) + 1

    if len(entry_starts) < 2:
        return None

    spans: list[EntrySpan] = []
    for idx, (start, title) in enumerate(entry_starts):
        end = entry_starts[idx + 1][0] if idx + 1 < len(entry_starts) else len(content)
        spans.append(EntrySpan(
            title=title,
            slug=sanitize_identifier(title),
            start=start,
            end=end,
            category="Feats",
        ))
    return spans
```

Update `_DETECTORS` list:

```python
_DETECTORS = [
    detect_spell_entries,
    detect_feat_entries,
]
```

- [ ] **Step 2: Write tests for feat detection**

Add to `tests/test_entry_splitter.py`:

```python
from scripts.ingest_srd35.entry_splitter import detect_feat_entries


SAMPLE_FEATS = (
    "ACROBATIC [GENERAL]\n"
    "Benefit: You get a +2 bonus on all Jump checks and Tumble checks.\n"
    "\n"
    "ATHLETIC [GENERAL]\n"
    "Benefit: You get a +2 bonus on all Climb checks and Swim checks.\n"
    "\n"
    "POWER ATTACK [GENERAL]\n"
    "Prerequisite: Str 13.\n"
    "Benefit: On your action, before making attack rolls for a round, you may choose to subtract a number from all melee attack rolls and add the same number to all melee damage rolls.\n"
)


class DetectFeatEntriesTests(unittest.TestCase):
    def test_detects_three_feats(self) -> None:
        spans = detect_feat_entries(SAMPLE_FEATS)
        self.assertIsNotNone(spans)
        self.assertEqual(len(spans), 3)
        self.assertEqual(spans[0].title, "ACROBATIC [GENERAL]")
        self.assertEqual(spans[1].title, "ATHLETIC [GENERAL]")
        self.assertEqual(spans[2].title, "POWER ATTACK [GENERAL]")

    def test_feat_category(self) -> None:
        spans = detect_feat_entries(SAMPLE_FEATS)
        for span in spans:
            self.assertEqual(span.category, "Feats")

    def test_epic_tag(self) -> None:
        content = (
            "EPIC FORTITUDE [EPIC]\n"
            "Benefit: You gain a +4 bonus on all Fortitude saving throws.\n"
            "\n"
            "EPIC REFLEXES [EPIC]\n"
            "Benefit: You gain a +4 bonus on all Reflex saving throws.\n"
        )
        spans = detect_feat_entries(content)
        self.assertIsNotNone(spans)
        self.assertEqual(len(spans), 2)

    def test_single_feat_returns_none(self) -> None:
        content = "ACROBATIC [GENERAL]\nBenefit: +2 bonus on Jump and Tumble.\n"
        result = detect_feat_entries(content)
        self.assertIsNone(result)

    def test_non_feat_returns_none(self) -> None:
        content = "Dwarves are a stoic race.\nThey live underground.\n"
        result = detect_feat_entries(content)
        self.assertIsNone(result)
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_entry_splitter.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/ingest_srd35/entry_splitter.py tests/test_entry_splitter.py
git commit -m "feat(ingestion): add feat entry detector

Detects ALL CAPS NAME [TAG] patterns for GENERAL, FIGHTER,
METAMAGIC, ITEM CREATION, EPIC, DIVINE, PSIONIC tags.

Part of #60 — Phase A entry-aware ingestion, PR 2."
```

### Task 7: Skill detector

**Files:**
- Modify: `scripts/ingest_srd35/entry_splitter.py`
- Modify: `tests/test_entry_splitter.py`

- [ ] **Step 1: Write detect_skill_entries**

Add to `scripts/ingest_srd35/entry_splitter.py`:

```python
_ABILITIES = {"STR", "DEX", "CON", "INT", "WIS", "CHA"}
_SKILL_PATTERN = re.compile(
    r"^[A-Z][A-Z \-']+\((" + "|".join(_ABILITIES) + r")\)\s*$"
)


def detect_skill_entries(content: str) -> list[EntrySpan] | None:
    """Detect skill entries by ALL CAPS NAME (ABILITY) pattern.

    Returns None if fewer than 2 skills detected.
    """
    lines = content.split("\n")
    entry_starts: list[tuple[int, str]] = []

    char_offset = 0
    for line in lines:
        stripped = line.strip()
        if _SKILL_PATTERN.match(stripped):
            entry_starts.append((char_offset, stripped))
        char_offset += len(line) + 1

    if len(entry_starts) < 2:
        return None

    spans: list[EntrySpan] = []
    for idx, (start, title) in enumerate(entry_starts):
        end = entry_starts[idx + 1][0] if idx + 1 < len(entry_starts) else len(content)
        spans.append(EntrySpan(
            title=title,
            slug=sanitize_identifier(title),
            start=start,
            end=end,
            category="Skills",
        ))
    return spans
```

Update `_DETECTORS`:

```python
_DETECTORS = [
    detect_spell_entries,
    detect_feat_entries,
    detect_skill_entries,
]
```

- [ ] **Step 2: Write tests**

Add to `tests/test_entry_splitter.py`:

```python
from scripts.ingest_srd35.entry_splitter import detect_skill_entries


SAMPLE_SKILLS = (
    "APPRAISE (INT)\n"
    "Check: You can appraise common objects within 10% of their value.\n"
    "Action: Appraising an item takes 1 minute.\n"
    "\n"
    "BALANCE (DEX)\n"
    "Check: You can walk on a precarious surface.\n"
    "Action: None.\n"
)


class DetectSkillEntriesTests(unittest.TestCase):
    def test_detects_two_skills(self) -> None:
        spans = detect_skill_entries(SAMPLE_SKILLS)
        self.assertIsNotNone(spans)
        self.assertEqual(len(spans), 2)
        self.assertEqual(spans[0].title, "APPRAISE (INT)")
        self.assertEqual(spans[1].title, "BALANCE (DEX)")

    def test_skill_category(self) -> None:
        spans = detect_skill_entries(SAMPLE_SKILLS)
        for span in spans:
            self.assertEqual(span.category, "Skills")

    def test_non_skill_returns_none(self) -> None:
        content = "Some general combat text.\n"
        result = detect_skill_entries(content)
        self.assertIsNone(result)
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_entry_splitter.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/ingest_srd35/entry_splitter.py tests/test_entry_splitter.py
git commit -m "feat(ingestion): add skill entry detector

Detects ALL CAPS NAME (ABILITY) patterns for STR/DEX/CON/INT/WIS/CHA.

Part of #60 — Phase A entry-aware ingestion, PR 2."
```

### Task 8: Condition detector

**Files:**
- Modify: `scripts/ingest_srd35/entry_splitter.py`
- Modify: `tests/test_entry_splitter.py`

- [ ] **Step 1: Write detect_condition_entries**

Conditions are trickier — they only appear in the CONDITIONS section of AbilitiesandConditions.rtf. Detection: within content that starts with condition-like preamble, each condition is a short title-cased line followed by a description paragraph.

Add to `scripts/ingest_srd35/entry_splitter.py`:

```python
_KNOWN_CONDITIONS = {
    "Ability Damaged", "Ability Drained", "Blinded", "Blown Away",
    "Checked", "Confused", "Cowering", "Dazed", "Dazzled", "Dead",
    "Deafened", "Disabled", "Dying", "Energy Drained", "Entangled",
    "Exhausted", "Fascinated", "Fatigued", "Flat-Footed", "Frightened",
    "Grappling", "Helpless", "Incorporeal", "Invisible", "Knocked Down",
    "Nauseated", "Panicked", "Paralyzed", "Petrified", "Pinned",
    "Prone", "Shaken", "Sickened", "Stable", "Staggered", "Stunned",
    "Turned", "Unconscious",
}


def detect_condition_entries(content: str) -> list[EntrySpan] | None:
    """Detect condition entries by known condition names on their own line.

    Returns None if fewer than 2 conditions detected.
    Only fires when the content contains many known condition names.
    """
    lines = content.split("\n")
    entry_starts: list[tuple[int, str]] = []

    char_offset = 0
    for line in lines:
        stripped = line.strip()
        if stripped in _KNOWN_CONDITIONS:
            entry_starts.append((char_offset, stripped))
        char_offset += len(line) + 1

    if len(entry_starts) < 5:
        # Require at least 5 to avoid false positives on content
        # that happens to mention a condition name
        return None

    spans: list[EntrySpan] = []
    for idx, (start, title) in enumerate(entry_starts):
        end = entry_starts[idx + 1][0] if idx + 1 < len(entry_starts) else len(content)
        spans.append(EntrySpan(
            title=title,
            slug=sanitize_identifier(title),
            start=start,
            end=end,
            category="Conditions",
        ))
    return spans
```

Update `_DETECTORS`:

```python
_DETECTORS = [
    detect_spell_entries,
    detect_feat_entries,
    detect_skill_entries,
    detect_condition_entries,
]
```

- [ ] **Step 2: Write tests**

Add to `tests/test_entry_splitter.py`:

```python
from scripts.ingest_srd35.entry_splitter import detect_condition_entries


SAMPLE_CONDITIONS = (
    "If more than one condition affects a character, apply them all.\n"
    "Ability Damaged\n"
    "The character has temporarily lost 1 or more ability score points.\n"
    "\n"
    "Ability Drained\n"
    "The character has permanently lost 1 or more ability score points.\n"
    "\n"
    "Blinded\n"
    "The character cannot see. He takes a -2 penalty to Armor Class.\n"
    "\n"
    "Confused\n"
    "A confused character's actions are determined by rolling d%.\n"
    "\n"
    "Cowering\n"
    "The character is frozen in fear.\n"
    "\n"
    "Dazed\n"
    "The creature is unable to act normally.\n"
)


class DetectConditionEntriesTests(unittest.TestCase):
    def test_detects_conditions(self) -> None:
        spans = detect_condition_entries(SAMPLE_CONDITIONS)
        self.assertIsNotNone(spans)
        self.assertEqual(len(spans), 6)
        self.assertEqual(spans[0].title, "Ability Damaged")
        self.assertEqual(spans[1].title, "Ability Drained")
        self.assertEqual(spans[2].title, "Blinded")

    def test_condition_category(self) -> None:
        spans = detect_condition_entries(SAMPLE_CONDITIONS)
        for span in spans:
            self.assertEqual(span.category, "Conditions")

    def test_preamble_before_first_condition(self) -> None:
        spans = detect_condition_entries(SAMPLE_CONDITIONS)
        # First condition starts after the preamble line
        first_content = SAMPLE_CONDITIONS[spans[0].start : spans[0].end]
        self.assertTrue(first_content.startswith("Ability Damaged"))

    def test_few_conditions_returns_none(self) -> None:
        content = (
            "Blinded\nCannot see.\n"
            "Deafened\nCannot hear.\n"
        )
        result = detect_condition_entries(content)
        self.assertIsNone(result)  # Only 2, need at least 5

    def test_non_condition_content_returns_none(self) -> None:
        content = "Dwarves are a stoic race.\n"
        result = detect_condition_entries(content)
        self.assertIsNone(result)
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_entry_splitter.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/ingest_srd35/entry_splitter.py tests/test_entry_splitter.py
git commit -m "feat(ingestion): add condition entry detector

Uses known-condition-name lookup. Requires 5+ matches to avoid
false positives. category='Conditions'.

Part of #60 — Phase A entry-aware ingestion, PR 2."
```

### Task 9: Run full test suite and raise PR 2

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Push and open PR**

```bash
git push -u origin worktree-chunker-audit
```

Create PR with title: `feat(ingestion): feat, skill, condition detectors (#60 PR 2/4)`

---

## PR 3: Chunker Multi-Chunk Output

### Task 10: Refactor chunker pipeline for 1-to-many

**Files:**
- Modify: `scripts/chunker/pipeline.py:42-65,132-140`
- Modify: `tests/test_chunker.py`

- [ ] **Step 1: Write failing test for parent-child output**

Add to `tests/test_chunker.py`:

```python
class HierarchyTests(unittest.TestCase):
    """Tests for parent-child chunk relationships (Phase B)."""

    def _make_canonical_doc(self, document_id: str, content: str, **locator_extra) -> dict:
        locator = {
            "section_path": ["Spells", document_id.split("::")[-1]],
            "source_location": f"Spells.rtf#001_{document_id.split('::')[-1]}",
            **locator_extra,
        }
        return {
            "document_id": document_id,
            "source_ref": {
                "source_id": "srd_35_fixture",
                "title": "System Reference Document",
                "edition": "3.5e",
                "source_type": "srd",
                "authority_level": "official_reference",
            },
            "locator": locator,
            "content": content,
        }

    def _run_chunker_on_docs(self, docs: list[dict]) -> list[dict]:
        """Write canonical docs to temp dir and run chunker."""
        with tempfile.TemporaryDirectory() as tmp:
            canonical_root = Path(tmp) / "canonical"
            canonical_root.mkdir()
            for i, doc in enumerate(docs):
                path = canonical_root / f"doc_{i:03d}.json"
                path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
            output_root = Path(tmp) / "chunks"
            chunk_source(
                canonical_root=canonical_root,
                output_root=output_root,
                repo_root=REPO_ROOT,
                source_id="srd_35_fixture",
            )
            chunks = []
            for p in sorted(output_root.glob("*.json")):
                if p.name != "chunk_report.json":
                    chunks.append(json.loads(p.read_text(encoding="utf-8")))
        return chunks

    def test_small_doc_produces_parent_only(self) -> None:
        doc = self._make_canonical_doc(
            "srd_35::spells::sanctuary",
            "Sanctuary\nAbjuration\nLevel: Clr 1\n\nShort spell.",
        )
        chunks = self._run_chunker_on_docs([doc])
        self.assertEqual(len(chunks), 1)
        self.assertNotIn("parent_chunk_id", chunks[0])

    def test_large_doc_produces_parent_and_children(self) -> None:
        # Create a doc large enough to trigger child splitting
        large_content = "Entry Header\nAbjuration\nLevel: Clr 1\n\n"
        # Add enough paragraphs to exceed the threshold
        for i in range(20):
            large_content += f"Paragraph {i}: " + "x" * 500 + "\n\n"
        doc = self._make_canonical_doc("srd_35::spells::big_spell", large_content)
        chunks = self._run_chunker_on_docs([doc])

        parents = [c for c in chunks if "parent_chunk_id" not in c]
        children = [c for c in chunks if "parent_chunk_id" in c]
        self.assertEqual(len(parents), 1)
        self.assertGreater(len(children), 0)
        # All children point to the parent
        for child in children:
            self.assertEqual(child["parent_chunk_id"], parents[0]["chunk_id"])

    def test_child_sibling_adjacency(self) -> None:
        large_content = "Entry\nAbjuration\nLevel: Clr 1\n\n"
        for i in range(20):
            large_content += f"Paragraph {i}: " + "x" * 500 + "\n\n"
        doc = self._make_canonical_doc("srd_35::spells::big", large_content)
        chunks = self._run_chunker_on_docs([doc])

        children = [c for c in chunks if "parent_chunk_id" in c]
        if len(children) < 2:
            self.skipTest("Not enough children for adjacency test")
        # First child has no previous
        self.assertNotIn("previous_chunk_id", children[0])
        # Last child has no next
        self.assertNotIn("next_chunk_id", children[-1])
        # Middle children link correctly
        for i in range(1, len(children)):
            self.assertEqual(children[i].get("previous_chunk_id"), children[i - 1]["chunk_id"])
        for i in range(len(children) - 1):
            self.assertEqual(children[i].get("next_chunk_id"), children[i + 1]["chunk_id"])

    def test_child_ids_are_stable(self) -> None:
        large_content = "Entry\nAbjuration\nLevel: Clr 1\n\n"
        for i in range(20):
            large_content += f"Paragraph {i}: " + "x" * 500 + "\n\n"
        doc = self._make_canonical_doc("srd_35::spells::stable", large_content)
        chunks_1 = self._run_chunker_on_docs([doc])
        chunks_2 = self._run_chunker_on_docs([doc])
        ids_1 = [c["chunk_id"] for c in chunks_1]
        ids_2 = [c["chunk_id"] for c in chunks_2]
        self.assertEqual(ids_1, ids_2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_chunker.py::HierarchyTests -v`
Expected: FAIL — `test_large_doc_produces_parent_and_children` fails because current chunker always produces exactly 1 chunk per doc.

- [ ] **Step 3: Implement _build_chunks in chunker pipeline**

Replace `_build_chunk` (lines 42-65) in `scripts/chunker/pipeline.py` with:

```python
CHILD_THRESHOLD = 6000  # chars — docs above this get parent + children


def _build_parent_chunk(
    canonical_doc: dict,
    *,
    previous_chunk_id: str | None,
    next_chunk_id: str | None,
) -> dict:
    document_id = canonical_doc["document_id"]
    section_path = canonical_doc.get("locator", {}).get("section_path", [])
    content = canonical_doc.get("content", "")

    chunk: dict = {
        "chunk_id": _chunk_id(document_id),
        "document_id": document_id,
        "source_ref": canonical_doc["source_ref"],
        "locator": canonical_doc["locator"],
        "chunk_type": classify_chunk_type(section_path, content),
        "content": content,
        "chunk_version": CHUNK_VERSION,
    }
    if previous_chunk_id is not None:
        chunk["previous_chunk_id"] = previous_chunk_id
    if next_chunk_id is not None:
        chunk["next_chunk_id"] = next_chunk_id
    return chunk


def _split_into_children(
    canonical_doc: dict,
    parent_chunk_id: str,
) -> list[dict]:
    """Split large entry content into child chunks at paragraph boundaries."""
    content = canonical_doc.get("content", "")
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

    if len(paragraphs) <= 1:
        return []

    # Group paragraphs into children targeting ~2K chars each.
    groups: list[list[str]] = []
    current_group: list[str] = []
    current_size = 0
    for para in paragraphs:
        if current_size > 0 and current_size + len(para) > 2000:
            groups.append(current_group)
            current_group = []
            current_size = 0
        current_group.append(para)
        current_size += len(para)
    if current_group:
        groups.append(current_group)

    if len(groups) <= 1:
        return []

    document_id = canonical_doc["document_id"]
    children: list[dict] = []
    for idx, group in enumerate(groups):
        child_content = "\n\n".join(group)
        child_id = f"chunk::{document_id}::child_{idx + 1:03d}"
        child: dict = {
            "chunk_id": child_id,
            "document_id": document_id,
            "source_ref": canonical_doc["source_ref"],
            "locator": canonical_doc["locator"],
            "chunk_type": "paragraph_group",
            "content": child_content,
            "chunk_version": CHUNK_VERSION,
            "parent_chunk_id": parent_chunk_id,
        }
        children.append(child)

    # Wire sibling adjacency.
    for i, child in enumerate(children):
        if i > 0:
            child["previous_chunk_id"] = children[i - 1]["chunk_id"]
        if i < len(children) - 1:
            child["next_chunk_id"] = children[i + 1]["chunk_id"]

    return children


def _build_chunks(
    canonical_doc: dict,
    *,
    previous_chunk_id: str | None,
    next_chunk_id: str | None,
) -> list[dict]:
    """One canonical doc -> one or more chunks (parent + optional children)."""
    parent = _build_parent_chunk(
        canonical_doc,
        previous_chunk_id=previous_chunk_id,
        next_chunk_id=next_chunk_id,
    )
    content = canonical_doc.get("content", "")
    if len(content) <= CHILD_THRESHOLD:
        return [parent]

    children = _split_into_children(canonical_doc, parent["chunk_id"])
    return [parent] + children
```

- [ ] **Step 4: Update the chunk building loop**

In `chunk_source()`, replace lines 132-140:

```python
    # Build chunk objects with within-file adjacency only.
    chunks: list[tuple[str, dict]] = []
    for file_key, file_docs in by_file.items():
        n = len(file_docs)
        for i, (stem, doc) in enumerate(file_docs):
            prev_id = _chunk_id(file_docs[i - 1][1]["document_id"]) if i > 0 else None
            next_id = _chunk_id(file_docs[i + 1][1]["document_id"]) if i < n - 1 else None
            built = _build_chunks(doc, previous_chunk_id=prev_id, next_chunk_id=next_id)
            for chunk in built:
                chunks.append((stem, chunk))
```

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/test_chunker.py -v`
Expected: All tests PASS including new HierarchyTests.

Note: The existing `test_chunk_count_matches_canonical_doc_count` will still pass because fixture canonical docs are all small (under 6K chars), so no children are produced.

- [ ] **Step 6: Update golden chunk outputs**

Run: `UPDATE_GOLDEN=1 python -m pytest tests/test_chunker.py::GoldenChunkTests -v`
Expected: PASS (golden outputs regenerated — should be identical since fixtures don't trigger child splitting).

- [ ] **Step 7: Commit**

```bash
git add scripts/chunker/pipeline.py tests/test_chunker.py
git commit -m "feat(chunker): support parent-child chunk output

Refactors _build_chunk into _build_chunks (1-to-many). Docs exceeding
CHILD_THRESHOLD (6K chars) produce parent + paragraph_group children
with parent_chunk_id and sibling adjacency.

Part of #60 — Phase B hierarchical chunking, PR 3."
```

### Task 11: Update chunk report for parent/child stats

**Files:**
- Modify: `scripts/chunker/pipeline.py:160-178`
- Modify: `tests/test_chunker.py`

- [ ] **Step 1: Add parent_chunk_id to chunk_records and summary stats**

In the chunk report writing section of `chunk_source()`, update the record building:

```python
    chunk_records: list[dict] = []
    parent_count = 0
    child_count = 0
    for stem, chunk in chunks:
        chunk_path = output_root / f"{stem}.json"
        # Children need unique filenames — append child suffix
        if "parent_chunk_id" in chunk:
            child_suffix = chunk["chunk_id"].split("::")[-1]
            chunk_path = output_root / f"{stem}__{child_suffix}.json"
            child_count += 1
        else:
            parent_count += 1
        chunk_path.write_text(json.dumps(chunk, indent=2) + "\n", encoding="utf-8")
        try:
            display_path = str(chunk_path.relative_to(repo_root))
        except ValueError:
            display_path = str(chunk_path)
        record = {
            "chunk_id": chunk["chunk_id"],
            "document_id": chunk["document_id"],
            "chunk_type": chunk["chunk_type"],
            "chunk_path": display_path,
        }
        if "parent_chunk_id" in chunk:
            record["parent_chunk_id"] = chunk["parent_chunk_id"]
        chunk_records.append(record)
```

Update the report dict:

```python
    report = {
        "source_id": source_id,
        "chunked_at_utc": chunked_at,
        "strategy": CHUNK_VERSION,
        "chunk_count": len(chunk_records),
        "parent_count": parent_count,
        "child_count": child_count,
        "schema_validation": validation_result,
        "records": chunk_records,
    }
```

- [ ] **Step 2: Add test for report parent/child counts**

Add to `HierarchyTests` in `tests/test_chunker.py`:

```python
    def test_report_includes_parent_child_counts(self) -> None:
        large_content = "Entry\nAbjuration\nLevel: Clr 1\n\n"
        for i in range(20):
            large_content += f"Paragraph {i}: " + "x" * 500 + "\n\n"
        doc = self._make_canonical_doc("srd_35::spells::big", large_content)
        with tempfile.TemporaryDirectory() as tmp:
            canonical_root = Path(tmp) / "canonical"
            canonical_root.mkdir()
            (canonical_root / "doc_000.json").write_text(
                json.dumps(doc, indent=2), encoding="utf-8"
            )
            output_root = Path(tmp) / "chunks"
            chunk_source(
                canonical_root=canonical_root,
                output_root=output_root,
                repo_root=REPO_ROOT,
                source_id="srd_35_fixture",
            )
            report = json.loads((output_root / "chunk_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["parent_count"], 1)
        self.assertGreater(report["child_count"], 0)
        self.assertEqual(report["chunk_count"], report["parent_count"] + report["child_count"])
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_chunker.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/chunker/pipeline.py tests/test_chunker.py
git commit -m "feat(chunker): add parent/child counts to chunk report

Report now includes parent_count and child_count fields.
Child chunk records include parent_chunk_id. Child files get
unique names with child suffix.

Part of #60 — Phase B hierarchical chunking, PR 3."
```

### Task 12: Run full suite and raise PR 3

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Update golden outputs if needed**

Run: `UPDATE_GOLDEN=1 python -m pytest tests/test_chunker.py::GoldenChunkTests tests/test_golden_ingestion.py -v`
Expected: PASS

- [ ] **Step 3: Push and open PR**

```bash
git push -u origin worktree-chunker-audit
```

Create PR with title: `feat(chunker): parent-child hierarchical chunking (#60 PR 3/4)`

---

## PR 4: Structure-Aware Child Splitting

### Task 13: Stat block detection for child splitting

**Files:**
- Modify: `scripts/chunker/pipeline.py`
- Modify: `tests/test_chunker.py`

- [ ] **Step 1: Write tests for structure-aware splitting**

Add to `HierarchyTests` in `tests/test_chunker.py`:

```python
    def test_spell_stat_block_stays_together(self) -> None:
        """Stat block fields should be grouped in the first child."""
        content = (
            "Fireball\n"
            "Evocation [Fire]\n"
            "Level: Sor/Wiz 3\n"
            "Components: V, S, M\n"
            "Casting Time: 1 standard action\n"
            "Range: Long (400 ft. + 40 ft./level)\n"
            "Area: 20-ft.-radius spread\n"
            "Duration: Instantaneous\n"
            "Saving Throw: Reflex half\n"
            "Spell Resistance: Yes\n"
            "\n"
            + "A fireball spell is an explosion of flame. " * 50 + "\n\n"
            + "The glowing bead created by fireball. " * 50 + "\n\n"
            + "Material Component: A tiny ball of bat guano and sulfur.\n"
        )
        doc = self._make_canonical_doc("srd_35::spells::fireball", content)
        chunks = self._run_chunker_on_docs([doc])
        children = [c for c in chunks if "parent_chunk_id" in c]
        if not children:
            self.skipTest("Content not large enough to trigger splitting")
        # First child should contain the stat block fields
        first_child = children[0]
        self.assertIn("Level:", first_child["content"])
        self.assertIn("Spell Resistance:", first_child["content"])
```

- [ ] **Step 2: Run test to verify it fails or passes with current impl**

Run: `python -m pytest tests/test_chunker.py::HierarchyTests::test_spell_stat_block_stays_together -v`

If the paragraph-boundary splitter from Task 10 already keeps the stat block together (because the stat block fields are separated by `\n` not `\n\n`), this test may already pass. If not, proceed to step 3.

- [ ] **Step 3: Enhance _split_into_children with stat block detection**

Update `_split_into_children` in `scripts/chunker/pipeline.py`:

```python
_STAT_BLOCK_LABELS = {
    "level:", "components:", "casting time:", "range:", "target:",
    "targets:", "effect:", "area:", "duration:", "saving throw:",
    "spell resistance:", "prerequisite:", "benefit:", "normal:",
    "special:", "check:", "action:", "try again:", "synergy:",
}


def _is_stat_block_line(line: str) -> bool:
    lower = line.strip().lower()
    return any(lower.startswith(label) for label in _STAT_BLOCK_LABELS)


def _split_into_children(
    canonical_doc: dict,
    parent_chunk_id: str,
) -> list[dict]:
    """Split large entry content into child chunks with structure awareness.

    Priority: stat block child first, then paragraph groups.
    """
    content = canonical_doc.get("content", "")
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

    if len(paragraphs) <= 1:
        return []

    # Detect stat block: contiguous paragraphs where lines match stat labels.
    stat_block_end = 0
    for i, para in enumerate(paragraphs):
        lines = para.split("\n")
        if any(_is_stat_block_line(line) for line in lines):
            stat_block_end = i + 1
        elif stat_block_end > 0:
            break  # stat block ended

    # Build groups: stat block first, then paragraph groups.
    groups: list[list[str]] = []
    if stat_block_end > 0:
        groups.append(paragraphs[:stat_block_end])
        remaining = paragraphs[stat_block_end:]
    else:
        remaining = paragraphs

    # Group remaining paragraphs targeting ~2K chars.
    current_group: list[str] = []
    current_size = 0
    for para in remaining:
        if current_size > 0 and current_size + len(para) > 2000:
            groups.append(current_group)
            current_group = []
            current_size = 0
        current_group.append(para)
        current_size += len(para)
    if current_group:
        groups.append(current_group)

    if len(groups) <= 1:
        return []

    document_id = canonical_doc["document_id"]
    children: list[dict] = []
    for idx, group in enumerate(groups):
        child_content = "\n\n".join(group)
        child_id = f"chunk::{document_id}::child_{idx + 1:03d}"
        child: dict = {
            "chunk_id": child_id,
            "document_id": document_id,
            "source_ref": canonical_doc["source_ref"],
            "locator": canonical_doc["locator"],
            "chunk_type": "paragraph_group",
            "content": child_content,
            "chunk_version": CHUNK_VERSION,
            "parent_chunk_id": parent_chunk_id,
        }
        children.append(child)

    # Wire sibling adjacency.
    for i, child in enumerate(children):
        if i > 0:
            child["previous_chunk_id"] = children[i - 1]["chunk_id"]
        if i < len(children) - 1:
            child["next_chunk_id"] = children[i + 1]["chunk_id"]

    return children
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_chunker.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/chunker/pipeline.py tests/test_chunker.py
git commit -m "feat(chunker): structure-aware child splitting with stat block detection

Stat block fields (Level, Components, Casting Time, etc.) are grouped
into the first child. Remaining content split into paragraph groups
targeting ~2K chars. Recognized labels cover spells, feats, and skills.

Part of #60 — Phase B hierarchical chunking, PR 4."
```

### Task 14: Run full suite and raise PR 4

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Update golden outputs**

Run: `UPDATE_GOLDEN=1 python -m pytest tests/test_chunker.py::GoldenChunkTests tests/test_golden_ingestion.py -v`
Expected: PASS

- [ ] **Step 3: Push and open PR**

```bash
git push -u origin worktree-chunker-audit
```

Create PR with title: `feat(chunker): structure-aware child splitting (#60 PR 4/4)`
