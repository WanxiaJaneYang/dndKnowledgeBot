from __future__ import annotations

import unittest

from scripts.ingest_srd35.sectioning import split_sections_from_blocks


def _block(text: str, **fields) -> dict:
    base = {
        "block_id": f"b{abs(hash(text)) % 10000:04d}",
        "block_type": "paragraph",
        "text": text,
        "font_size": 24,
        "starts_with_bold": False,
        "all_bold": False,
    }
    base.update(fields)
    return base


def _annotated(block: dict, **annotations) -> dict:
    block.update(annotations)
    return block


class EntryDrivenSectioningTests(unittest.TestCase):
    def test_one_entry_one_section(self) -> None:
        blocks = [
            _annotated(
                _block("Sanctuary"),
                entry_index=0, entry_role="title", entry_type="spell",
                entry_category="Spells", entry_chunk_type="spell_entry",
                entry_title="Sanctuary", shape_family="entry_with_statblock",
            ),
            _annotated(
                _block("Abjuration", font_size=20),
                entry_index=0, entry_role="subtitle", entry_type="spell",
                entry_category="Spells", entry_chunk_type="spell_entry",
                entry_title="Sanctuary", shape_family="entry_with_statblock",
            ),
            _annotated(
                _block("Level: Clr 1", font_size=20, starts_with_bold=True),
                entry_index=0, entry_role="stat_field", entry_type="spell",
                entry_category="Spells", entry_chunk_type="spell_entry",
                entry_title="Sanctuary", shape_family="entry_with_statblock",
            ),
        ]
        sections = split_sections_from_blocks("SpellsS", blocks)
        self.assertEqual(len(sections), 1)
        s = sections[0]
        self.assertEqual(s["section_title"], "Sanctuary")
        self.assertIn("Sanctuary\nAbjuration\nLevel: Clr 1", s["content"])
        self.assertIn("entry_metadata", s)
        meta = s["entry_metadata"]
        self.assertEqual(meta["entry_type"], "spell")
        self.assertEqual(meta["entry_category"], "Spells")
        self.assertEqual(meta["entry_chunk_type"], "spell_entry")
        self.assertEqual(meta["entry_title"], "Sanctuary")
        self.assertEqual(meta["entry_index"], 0)

    def test_two_entries_two_sections(self) -> None:
        blocks = []
        for idx, title in enumerate(["Sanctuary", "Scare"]):
            for role, text, size, bold in [
                ("title", title, 24, False),
                ("subtitle", "Abjuration", 20, False),
                ("stat_field", "Level: x", 20, True),
            ]:
                blocks.append(_annotated(
                    _block(text, font_size=size, starts_with_bold=bold),
                    entry_index=idx, entry_role=role, entry_type="spell",
                    entry_category="Spells", entry_chunk_type="spell_entry",
                    entry_title=title, shape_family="entry_with_statblock",
                ))
        sections = split_sections_from_blocks("SpellsS", blocks)
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0]["section_title"], "Sanctuary")
        self.assertEqual(sections[1]["section_title"], "Scare")

    def test_unannotated_gap_becomes_separate_section(self) -> None:
        blocks = [
            _block("OGL boilerplate text here."),
            _annotated(
                _block("Sanctuary"),
                entry_index=0, entry_role="title", entry_type="spell",
                entry_category="Spells", entry_chunk_type="spell_entry",
                entry_title="Sanctuary", shape_family="entry_with_statblock",
            ),
            _annotated(
                _block("Abjuration", font_size=20),
                entry_index=0, entry_role="subtitle", entry_type="spell",
                entry_category="Spells", entry_chunk_type="spell_entry",
                entry_title="Sanctuary", shape_family="entry_with_statblock",
            ),
            _annotated(
                _block("Level: Clr 1", font_size=20, starts_with_bold=True),
                entry_index=0, entry_role="stat_field", entry_type="spell",
                entry_category="Spells", entry_chunk_type="spell_entry",
                entry_title="Sanctuary", shape_family="entry_with_statblock",
            ),
        ]
        sections = split_sections_from_blocks("SpellsS", blocks)
        # Expect 2 sections: preamble (no entry_metadata) + Sanctuary
        self.assertEqual(len(sections), 2)
        self.assertNotIn("entry_metadata", sections[0])
        self.assertIn("entry_metadata", sections[1])


class HeadingCandidateFallbackTests(unittest.TestCase):
    def test_no_annotations_falls_back_to_heading_candidates(self) -> None:
        # Today's behavior must continue when no entry_index is present.
        blocks = [
            {"block_id": "b0001", "block_type": "heading_candidate", "text": "Some Heading", "font_size": 24, "starts_with_bold": False, "all_bold": False},
            {"block_id": "b0002", "block_type": "paragraph", "text": "Some long body content " * 5, "font_size": 24, "starts_with_bold": False, "all_bold": False},
        ]
        sections = split_sections_from_blocks("Test", blocks)
        # Old logic produces a section titled "Some Heading" with the body content.
        self.assertGreater(len(sections), 0)
        self.assertNotIn("entry_metadata", sections[0])


if __name__ == "__main__":
    unittest.main()
