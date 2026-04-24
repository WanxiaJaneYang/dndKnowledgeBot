from __future__ import annotations

import unittest

from scripts.ingest_srd35.content_types import ContentTypeConfig
from scripts.ingest_srd35.entry_annotator import (
    annotate_entries,
    EntryAnnotationConflict,
)


SPELL_CFG = ContentTypeConfig(
    name="spell", category="Spells", chunk_type="spell_entry",
    shape="entry_with_statblock",
    shape_params={
        "max_title_len": 80, "max_subtitle_len": 80,
        "min_fields": 2, "field_pattern": r"^[A-Z][\w '/-]+:",
    },
    file_match=["Spells*.rtf"],
)


def _block(text: str, *, font_size: int, starts_with_bold: bool = False, all_bold: bool = False) -> dict:
    return {
        "block_id": f"b{abs(hash(text)) % 10000:04d}",
        "block_type": "paragraph",
        "text": text,
        "font_size": font_size,
        "starts_with_bold": starts_with_bold,
        "all_bold": all_bold,
    }


class EntryWithStatblockHappyPathTests(unittest.TestCase):
    def test_single_spell_detected(self) -> None:
        blocks = [
            _block("Sanctuary",          font_size=24),
            _block("Abjuration",         font_size=20),
            _block("Level: Clr 1",       font_size=20, starts_with_bold=True),
            _block("Components: V, S",   font_size=20, starts_with_bold=True),
            _block("Description text.",  font_size=24),
        ]
        result = annotate_entries(blocks, file_name="SpellsS.rtf", content_types=[SPELL_CFG])
        roles = [b.get("entry_role") for b in result]
        self.assertEqual(roles, ["title", "subtitle", "stat_field", "stat_field", "description"])
        for b in result:
            self.assertEqual(b["entry_index"], 0)
            self.assertEqual(b["entry_type"], "spell")
            self.assertEqual(b["entry_category"], "Spells")
            self.assertEqual(b["entry_chunk_type"], "spell_entry")
            self.assertEqual(b["entry_title"], "Sanctuary")

    def test_two_spells_distinct_indices(self) -> None:
        blocks = [
            _block("Sanctuary",        font_size=24),
            _block("Abjuration",       font_size=20),
            _block("Level: Clr 1",     font_size=20, starts_with_bold=True),
            _block("Components: V, S", font_size=20, starts_with_bold=True),
            _block("Scare",            font_size=24),
            _block("Necromancy",       font_size=20),
            _block("Level: Brd 2",     font_size=20, starts_with_bold=True),
            _block("Components: V, S", font_size=20, starts_with_bold=True),
        ]
        result = annotate_entries(blocks, file_name="SpellsS.rtf", content_types=[SPELL_CFG])
        indices = [b["entry_index"] for b in result]
        self.assertEqual(indices, [0, 0, 0, 0, 1, 1, 1, 1])
        titles = {b["entry_title"] for b in result}
        self.assertEqual(titles, {"Sanctuary", "Scare"})


class EntryWithStatblockGuardTests(unittest.TestCase):
    def test_subtitle_same_size_as_title_rejected(self) -> None:
        blocks = [
            _block("Looks Like Title", font_size=20),
            _block("Abjuration",       font_size=20),
            _block("Level: Clr 1",     font_size=20, starts_with_bold=True),
            _block("Components: V, S", font_size=20, starts_with_bold=True),
        ]
        result = annotate_entries(blocks, file_name="SpellsS.rtf", content_types=[SPELL_CFG])
        self.assertTrue(all("entry_index" not in b for b in result))

    def test_below_min_fields(self) -> None:
        blocks = [
            _block("Sanctuary",   font_size=24),
            _block("Abjuration",  font_size=20),
            _block("Level: Clr 1", font_size=20, starts_with_bold=True),
        ]
        result = annotate_entries(blocks, file_name="SpellsS.rtf", content_types=[SPELL_CFG])
        self.assertTrue(all("entry_index" not in b for b in result))

    def test_title_matching_field_pattern_rejected(self) -> None:
        blocks = [
            _block("Looking Like: A Field", font_size=24),  # matches field_pattern
            _block("Abjuration",            font_size=20),
            _block("Level: Clr 1",          font_size=20, starts_with_bold=True),
            _block("Components: V, S",      font_size=20, starts_with_bold=True),
        ]
        result = annotate_entries(blocks, file_name="SpellsS.rtf", content_types=[SPELL_CFG])
        self.assertTrue(all("entry_index" not in b for b in result))

    def test_empty_title_rejected(self) -> None:
        blocks = [
            _block("   ",                font_size=24),
            _block("Abjuration",         font_size=20),
            _block("Level: Clr 1",       font_size=20, starts_with_bold=True),
            _block("Components: V, S",   font_size=20, starts_with_bold=True),
        ]
        result = annotate_entries(blocks, file_name="SpellsS.rtf", content_types=[SPELL_CFG])
        self.assertTrue(all("entry_index" not in b for b in result))


class EntryWithStatblockBaselineDriftTests(unittest.TestCase):
    """Verify shape rule is robust to per-document font baseline drift."""
    def test_works_when_stat_blocks_dominate(self) -> None:
        # In a stat-block-heavy file, the IR baseline might be fs20, not fs24.
        # The shape rule should still match because it uses relational
        # predicates (subtitle.font_size < title.font_size), not absolute classes.
        blocks = [
            _block("Sanctuary",        font_size=24),  # title (larger than subtitle)
            _block("Abjuration",       font_size=20),  # subtitle
            _block("Level: Clr 1",     font_size=20, starts_with_bold=True),
            _block("Components: V, S", font_size=20, starts_with_bold=True),
        ]
        result = annotate_entries(blocks, file_name="SpellsS.rtf", content_types=[SPELL_CFG])
        self.assertEqual(result[0].get("entry_role"), "title")


CONDITION_CFG = ContentTypeConfig(
    name="condition", category="Conditions", chunk_type="condition_entry",
    shape="definition_list",
    shape_params={
        "min_blocks": 3,
        "term_pattern": r"^[A-Z][\w '/-]*:\s+\S",
    },
    file_match=["AbilitiesandConditions.rtf"],
)


class DefinitionListTests(unittest.TestCase):
    def test_three_conditions_detected(self) -> None:
        blocks = [
            _block("Blinded: cannot see", font_size=20, starts_with_bold=True),
            _block("Confused: rolls d%",  font_size=20, starts_with_bold=True),
            _block("Dazed: unable to act", font_size=20, starts_with_bold=True),
        ]
        result = annotate_entries(blocks, file_name="AbilitiesandConditions.rtf", content_types=[CONDITION_CFG])
        roles = [b.get("entry_role") for b in result]
        self.assertEqual(roles, ["definition", "definition", "definition"])
        titles = [b["entry_title"] for b in result]
        self.assertEqual(titles, ["Blinded", "Confused", "Dazed"])
        indices = [b["entry_index"] for b in result]
        self.assertEqual(indices, [0, 1, 2])

    def test_below_min_blocks(self) -> None:
        blocks = [
            _block("Blinded: cannot see", font_size=20, starts_with_bold=True),
            _block("Confused: rolls d%",  font_size=20, starts_with_bold=True),
        ]
        result = annotate_entries(blocks, file_name="AbilitiesandConditions.rtf", content_types=[CONDITION_CFG])
        self.assertTrue(all("entry_index" not in b for b in result))

    def test_size_change_breaks_run(self) -> None:
        blocks = [
            _block("Blinded: cannot see", font_size=20, starts_with_bold=True),
            _block("Confused: rolls d%",  font_size=20, starts_with_bold=True),
            _block("Dazed: unable to act", font_size=18, starts_with_bold=True),  # different size
            _block("Frightened: flee",    font_size=18, starts_with_bold=True),
        ]
        result = annotate_entries(blocks, file_name="AbilitiesandConditions.rtf", content_types=[CONDITION_CFG])
        # First run: 2 blocks at fs20 (below min_blocks=3) → no annotation
        # Second run: 2 blocks at fs18 (below min_blocks=3) → no annotation
        self.assertTrue(all("entry_index" not in b for b in result))


class ConflictTests(unittest.TestCase):
    def test_re_run_raises(self) -> None:
        blocks = [
            _block("Sanctuary",        font_size=24),
            _block("Abjuration",       font_size=20),
            _block("Level: Clr 1",     font_size=20, starts_with_bold=True),
            _block("Components: V, S", font_size=20, starts_with_bold=True),
        ]
        annotate_entries(blocks, file_name="SpellsS.rtf", content_types=[SPELL_CFG])
        with self.assertRaises(EntryAnnotationConflict):
            annotate_entries(blocks, file_name="SpellsS.rtf", content_types=[SPELL_CFG])

    def test_overlapping_matches_raise(self) -> None:
        # Construct a degenerate case where two configs both match the same range.
        spell_loose = ContentTypeConfig(
            name="spell_loose", category="Spells", chunk_type="spell_entry",
            shape="entry_with_statblock",
            shape_params={
                "max_title_len": 80, "max_subtitle_len": 80,
                "min_fields": 1, "field_pattern": r"^[A-Z][\w '/-]+:",
            },
            file_match=None,
        )
        spell_loose_b = ContentTypeConfig(
            name="spell_loose_b", category="Spells", chunk_type="spell_entry",
            shape="entry_with_statblock",
            shape_params={
                "max_title_len": 80, "max_subtitle_len": 80,
                "min_fields": 1, "field_pattern": r"^[A-Z][\w '/-]+:",
            },
            file_match=None,
        )
        blocks = [
            _block("Sanctuary",     font_size=24),
            _block("Abjuration",    font_size=20),
            _block("Level: Clr 1",  font_size=20, starts_with_bold=True),
        ]
        with self.assertRaises(EntryAnnotationConflict):
            annotate_entries(blocks, file_name="any.rtf", content_types=[spell_loose, spell_loose_b])


class EligibilityTests(unittest.TestCase):
    def test_excluded_type_does_not_run(self) -> None:
        # Spell config restricted to Spells*.rtf; the file doesn't match.
        blocks = [
            _block("Sanctuary",     font_size=24),
            _block("Abjuration",    font_size=20),
            _block("Level: Clr 1",  font_size=20, starts_with_bold=True),
            _block("Components: V", font_size=20, starts_with_bold=True),
        ]
        result = annotate_entries(blocks, file_name="Description.rtf", content_types=[SPELL_CFG])
        self.assertTrue(all("entry_index" not in b for b in result))


class MultiTypeOverlapTests(unittest.TestCase):
    def test_description_region_overlapping_other_type_raises(self) -> None:
        # Spell entry's description region (blocks 4-6 — there's no next
        # entry title in this file) overlaps with the condition
        # definition_list match starting at block 4. Both types eligible
        # because file_name matches the spell file_match glob.
        spell = SPELL_CFG  # file_match=["Spells*.rtf"]
        cond = ContentTypeConfig(
            name="condition", category="Conditions", chunk_type="condition_entry",
            shape="definition_list",
            shape_params={"min_blocks": 3, "term_pattern": r"^[A-Z][\w '/-]*:\s+\S"},
            file_match=None,  # always eligible
        )
        blocks = [
            _block("Sanctuary",        font_size=24),
            _block("Abjuration",       font_size=20),
            _block("Level: Clr 1",     font_size=20, starts_with_bold=True),
            _block("Components: V, S", font_size=20, starts_with_bold=True),
            _block("Blinded: cannot see", font_size=18, starts_with_bold=True),
            _block("Confused: rolls d%",  font_size=18, starts_with_bold=True),
            _block("Dazed: unable to act", font_size=18, starts_with_bold=True),
        ]
        with self.assertRaises(EntryAnnotationConflict):
            annotate_entries(blocks, file_name="SpellsS.rtf", content_types=[spell, cond])


class FileWideMonotonicEntryIndexTests(unittest.TestCase):
    def test_disjoint_multi_type_indices_are_globally_unique(self) -> None:
        # Codex P1: with disjoint matches from two types, entry_index must
        # be a single monotonic counter over the file, NOT per-type. Otherwise
        # downstream grouping by entry_index would see ambiguous duplicates.
        spell = ContentTypeConfig(
            name="spell", category="Spells", chunk_type="spell_entry",
            shape="entry_with_statblock",
            shape_params={
                "max_title_len": 80, "max_subtitle_len": 80,
                "min_fields": 2, "field_pattern": r"^[A-Z][\w '/-]+:",
            },
            file_match=None,
        )
        cond = ContentTypeConfig(
            name="condition", category="Conditions", chunk_type="condition_entry",
            shape="definition_list",
            shape_params={"min_blocks": 3, "term_pattern": r"^[A-Z][\w '/-]*:\s+\S"},
            file_match=None,
        )
        blocks = [
            # Conditions block first (single-block entries, indices 0..2 expected).
            _block("Blinded: cannot see", font_size=18, starts_with_bold=True),
            _block("Confused: rolls d%", font_size=18, starts_with_bold=True),
            _block("Dazed: unable to act", font_size=18, starts_with_bold=True),
            # Then a spell with sufficient gap (different fs, no bold-prefix
            # term_pattern match) so detectors don't overlap.
            _block("Sanctuary", font_size=24),
            _block("Abjuration", font_size=20),
            _block("Level: Clr 1", font_size=20, starts_with_bold=True),
            _block("Components: V, S", font_size=20, starts_with_bold=True),
        ]
        annotate_entries(blocks, file_name="any.rtf", content_types=[spell, cond])
        # Per-block sequence: 3 conditions (single-block entries 0,1,2) +
        # 1 spell with 4 blocks all sharing entry_index 3.
        annotated_indices = [b["entry_index"] for b in blocks if "entry_index" in b]
        self.assertEqual(annotated_indices, [0, 1, 2, 3, 3, 3, 3])
        # Distinct entries must have distinct globally-monotonic indices —
        # NOT per-type (which would have given conditions [0,1,2] and
        # spell [0]).
        per_entry_index_per_type = {}
        for b in blocks:
            if "entry_index" not in b:
                continue
            per_entry_index_per_type.setdefault(b["entry_type"], set()).add(b["entry_index"])
        # spell entry_index ∈ {3}; condition entry_indices ∈ {0,1,2}; intersection empty.
        spell_indices = per_entry_index_per_type["spell"]
        cond_indices = per_entry_index_per_type["condition"]
        self.assertEqual(spell_indices & cond_indices, set())


if __name__ == "__main__":
    unittest.main()
