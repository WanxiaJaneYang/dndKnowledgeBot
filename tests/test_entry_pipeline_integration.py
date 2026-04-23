from __future__ import annotations

import unittest
from pathlib import Path

from scripts.ingest_srd35.rtf_decoder import decode_rtf_spans
from scripts.ingest_srd35.extraction_ir import build_extraction_ir
from scripts.ingest_srd35.entry_annotator import annotate_entries
from scripts.ingest_srd35.sectioning import split_sections_from_blocks
from scripts.ingest_srd35.content_types import load_content_types


REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "srd_35_entries"


def _process_fixture(path: Path) -> list[dict]:
    """Run a fixture through decode -> IR -> annotate -> section."""
    rtf = path.read_text(encoding="latin-1")
    spans = decode_rtf_spans(rtf)
    ir = build_extraction_ir(file_name=path.name, spans=spans)
    config_text = (REPO_ROOT / "configs" / "content_types.yaml").read_text(encoding="utf-8")
    types = load_content_types(config_text)
    annotate_entries(ir["blocks"], file_name=path.name, content_types=types)
    return split_sections_from_blocks(path.stem, ir["blocks"])


class SpellsExcerptIntegrationTests(unittest.TestCase):
    def test_two_spells_become_two_entry_sections(self) -> None:
        sections = _process_fixture(FIXTURE_DIR / "SpellsExcerpt.rtf")
        entry_sections = [s for s in sections if "entry_metadata" in s]
        self.assertEqual(len(entry_sections), 2)
        titles = {s["entry_metadata"]["entry_title"] for s in entry_sections}
        self.assertEqual(titles, {"Sanctuary", "Scare"})
        for s in entry_sections:
            meta = s["entry_metadata"]
            self.assertEqual(meta["entry_category"], "Spells")
            self.assertEqual(meta["entry_chunk_type"], "spell_entry")


class FeatsExcerptIntegrationTests(unittest.TestCase):
    def test_two_feats_become_two_entry_sections(self) -> None:
        sections = _process_fixture(FIXTURE_DIR / "FeatsExcerpt.rtf")
        entry_sections = [s for s in sections if "entry_metadata" in s]
        self.assertEqual(len(entry_sections), 2)
        titles = [s["entry_metadata"]["entry_title"] for s in entry_sections]
        self.assertIn("ACROBATIC", titles)
        self.assertIn("POWER ATTACK", titles)


class ConditionsExcerptIntegrationTests(unittest.TestCase):
    def test_four_conditions_become_four_entry_sections(self) -> None:
        sections = _process_fixture(FIXTURE_DIR / "ConditionsExcerpt.rtf")
        entry_sections = [s for s in sections if "entry_metadata" in s]
        self.assertEqual(len(entry_sections), 4)
        titles = [s["entry_metadata"]["entry_title"] for s in entry_sections]
        self.assertEqual(titles, ["Blinded", "Confused", "Dazed", "Frightened"])
        for s in entry_sections:
            self.assertEqual(s["entry_metadata"]["entry_chunk_type"], "condition_entry")


if __name__ == "__main__":
    unittest.main()
