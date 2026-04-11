import unittest

from scripts.ingest_srd35.boundary_filter import apply_boundary_filters
from scripts.ingest_srd35.sectioning import sanitize_identifier


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
    def test_merges_boilerplate_opener_in_non_legal_file(self) -> None:
        candidates = [
            _candidate("Description", "This material is Open Game Content. Visit www.wizards.com for details."),
            _candidate("Alignment", "Alignment is a broad category describing ethical outlook."),
        ]
        accepted, decisions = apply_boundary_filters("Description", "Description.rtf", candidates)
        self.assertEqual(len(accepted), 1)
        self.assertIn("Visit www.wizards.com", accepted[0]["content"])
        self.assertEqual(decisions[0]["action"], "merged_forward")

    def test_keeps_legal_file_sections(self) -> None:
        candidates = [
            _candidate("LEGAL INFORMATION", "This legal text is primary content in this source."),
            _candidate("OPEN GAME LICENSE Version 1.0a", "License terms continue here in full detail."),
        ]
        accepted, decisions = apply_boundary_filters("Legal", "Legal.rtf", candidates)
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
            _candidate("Law", "Lawful Neutral, Lawful Evil, and Lawful Good entries follow inline."),
        ]
        accepted, decisions = apply_boundary_filters("Description", "Description.rtf", candidates)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(decisions[1]["reason_code"], "suspicious_short_or_truncated")

    def test_does_not_over_clean_valid_sections(self) -> None:
        candidates = [
            _candidate("FAVORED CLASS", "Each race has a favored class used for multiclass XP rules." * 3),
            _candidate("HUMANS", "Human race traits include bonus feat and extra skill points." * 3),
            _candidate("DWARVES", "Dwarf race traits include darkvision and stonecunning." * 3),
        ]
        accepted, _ = apply_boundary_filters("Races", "Races.rtf", candidates)
        self.assertEqual([section["section_title"] for section in accepted], ["FAVORED CLASS", "HUMANS", "DWARVES"])


if __name__ == "__main__":
    unittest.main()
