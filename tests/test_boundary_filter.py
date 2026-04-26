import unittest

from scripts.ingest_srd35.boundary_filter import apply_boundary_filters
from scripts.ingest_srd35.sectioning import sanitize_identifier


BOILERPLATE_PHRASES = {
    "visit",
    "www.wizards.com",
    "system reference document",
    "contains all of the",
}


def _candidate(title: str, content: str, paragraph_count: int = 1, table_rows: int = 0) -> dict:
    return {
        "section_title": title,
        "section_slug": sanitize_identifier(title),
        "content": content,
        "body_char_count": len(content),
        "block_start_index": 0,
        "block_end_index": 0,
        "block_start_id": "b0001",
        "block_end_id": "b0001",
        "block_type_counts": {"paragraph": paragraph_count, "table_row": table_rows},
    }


class BoundaryFilterTests(unittest.TestCase):
    def test_heading_detector_rejects_trailing_colon_labels(self) -> None:
        from scripts.ingest_srd35.sectioning import looks_like_heading

        self.assertFalse(looks_like_heading("Lawful Neutral, \"Judge\":"))
        self.assertFalse(looks_like_heading("Mithral:"))

    def test_merges_boilerplate_opener_in_non_legal_file(self) -> None:
        candidates = [
            _candidate("Description", "This material is Open Game Content. Visit www.wizards.com for details."),
            _candidate("Alignment", "Alignment is a broad category describing ethical outlook."),
        ]
        accepted, decisions = apply_boundary_filters(
            "Description",
            "Description.rtf",
            candidates,
            boilerplate_phrases=BOILERPLATE_PHRASES,
        )
        self.assertEqual(len(accepted), 1)
        self.assertIn("Visit www.wizards.com", accepted[0]["content"])
        self.assertEqual(decisions[0]["action"], "merged_forward")

    def test_keeps_legal_file_sections(self) -> None:
        candidates = [
            _candidate("LEGAL INFORMATION", "This legal text is primary content in this source."),
            _candidate("OPEN GAME LICENSE Version 1.0a", "License terms continue here in full detail."),
        ]
        accepted, decisions = apply_boundary_filters(
            "Legal",
            "Legal.rtf",
            candidates,
            boilerplate_phrases=BOILERPLATE_PHRASES,
        )
        self.assertEqual(len(accepted), 2)
        self.assertTrue(all(decision["action"] == "accepted" for decision in decisions[:2]))

    def test_merges_table_fragment_backward(self) -> None:
        candidates = [
            _candidate("Special Materials", "Special materials rules with context and constraints." * 4),
            _candidate("Ammunition", "Name | Cost | Weight |", paragraph_count=0, table_rows=3),
        ]
        accepted, decisions = apply_boundary_filters("SpecialMaterials", "SpecialMaterials.rtf", candidates)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(decisions[1]["action"], "merged_backward")

    def test_merges_suspicious_truncated_titles(self) -> None:
        candidates = [
            _candidate("The Nine Alignments", "Introductory alignment material." * 4),
            _candidate("“Law”", "Lawful Neutral, Lawful Evil, and Lawful Good entries follow inline."),
        ]
        accepted, decisions = apply_boundary_filters("Description", "Description.rtf", candidates)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(decisions[1]["reason_code"], "suspicious_short_or_truncated")

    def test_merges_table_label_titles(self) -> None:
        candidates = [
            _candidate("Special Materials", "Special materials rules with context and constraints." * 4),
            _candidate("Ammunition |", "Name | Cost | Weight |", paragraph_count=0, table_rows=2),
        ]
        accepted, decisions = apply_boundary_filters("SpecialMaterials", "SpecialMaterials.rtf", candidates)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(decisions[1]["reason_code"], "table_label_title")

    def test_keeps_uppercase_single_token_titles(self) -> None:
        candidates = [
            _candidate("THE NINE ALIGNMENTS", "Alignment overview text." * 4),
            _candidate("AGE", "Age category and aging effects table context." * 4),
        ]
        accepted, _ = apply_boundary_filters("Description", "Description.rtf", candidates)
        self.assertEqual([section["section_title"] for section in accepted], ["THE NINE ALIGNMENTS", "AGE"])

    def test_merges_named_table_headings(self) -> None:
        # "Table: X" headings (without "|") are table titles, not independent sections.
        candidates = [
            _candidate("EPIC FEATS", "Epic feat descriptions follow." * 5),
            _candidate("Table: Epic Leadership", "Leadership score table data."),
        ]
        accepted, decisions = apply_boundary_filters("EpicFeats", "EpicFeats.rtf", candidates)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(decisions[1]["reason_code"], "table_label_title")

    def test_does_not_over_clean_valid_sections(self) -> None:
        candidates = [
            _candidate("FAVORED CLASS", "Each race has a favored class used for multiclass XP rules." * 3),
            _candidate("HUMANS", "Human race traits include bonus feat and extra skill points." * 3),
            _candidate("DWARVES", "Dwarf race traits include darkvision and stonecunning." * 3),
        ]
        accepted, _ = apply_boundary_filters("Races", "Races.rtf", candidates)
        self.assertEqual([section["section_title"] for section in accepted], ["FAVORED CLASS", "HUMANS", "DWARVES"])

    def test_stat_field_lookalike_merged_backward(self) -> None:
        # Codex P1 regression cover: when entry detection didn't fire on an
        # eligible spell file, bold-prefixed stat-field lines (Components:,
        # Effect:, Range:) used to be merged back into the preceding entry
        # via the deleted _looks_spell_block_field rule. The vocabulary-free
        # replacement uses formatting (title_starts_with_bold) + generic
        # Word: shape, which catches the same case without a per-edition
        # word list.
        sanctuary = _candidate(
            "Sanctuary",
            "Any opponent attempting to strike the warded creature must save." * 3,
        )
        sanctuary["title_starts_with_bold"] = False
        sanctuary["title_font_size"] = 24

        # Title text matches what the sectioner actually produces: when a
        # heading_candidate block is "Components: V, S, DF", the sectioner
        # promotes the full block text to section_title.
        components_field = _candidate("Components: V, S, DF", "V, S, DF")
        components_field["title_starts_with_bold"] = True
        components_field["title_font_size"] = 20

        candidates = [sanctuary, components_field]
        accepted, decisions = apply_boundary_filters(
            "SpellsS", "SpellsS.rtf", candidates,
        )
        self.assertEqual(len(accepted), 1)
        self.assertIn("V, S, DF", accepted[0]["content"])
        self.assertEqual(decisions[1]["reason_code"], "stat_field_lookalike")
        self.assertEqual(decisions[1]["action"], "merged_backward")

    def test_stat_field_lookalike_only_fires_when_title_is_bold(self) -> None:
        # Same shape but no bold flag — must NOT trigger the new rule
        # (avoids false positives on regular sections that happen to start
        # with "Word: ...").
        components_unbold = _candidate("Components: V, S, DF", "V, S, DF")
        components_unbold["title_starts_with_bold"] = False
        components_unbold["title_font_size"] = 20

        accepted, decisions = apply_boundary_filters(
            "SpellsS", "SpellsS.rtf", [
                _candidate("Sanctuary", "long body content here." * 10),
                components_unbold,
            ],
        )
        # Falls through to the suspicious_short_or_truncated branch instead
        # (since the body is short), but NOT the stat_field_lookalike branch.
        self.assertNotEqual(decisions[1]["reason_code"], "stat_field_lookalike")

    def test_entry_annotated_section_accepted_unconditionally(self) -> None:
        # Entry-annotated sections bypass all heuristics (short body, suspicious title, etc.).
        short_entry = _candidate("Components", "V, S")
        short_entry["entry_metadata"] = {
            "entry_type": "spell",
            "entry_category": "spell",
            "entry_chunk_type": "spell_block",
            "entry_title": "Burning Hands",
            "entry_index": 0,
            "shape_family": "spell",
        }
        candidates = [
            _candidate("Burning Hands", "Evocation [Fire] spell description body content here." * 3),
            short_entry,
        ]
        accepted, decisions = apply_boundary_filters("SpellsA-B", "SpellsA-B.rtf", candidates)
        self.assertEqual(len(accepted), 2)
        self.assertEqual(decisions[1]["reason_code"], "entry_annotated")
        self.assertEqual(decisions[1]["action"], "accepted")


if __name__ == "__main__":
    unittest.main()
