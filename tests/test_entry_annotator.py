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


if __name__ == "__main__":
    unittest.main()
