from __future__ import annotations

import unittest
from pathlib import Path

from scripts.ingest_srd35.rtf_decoder import decode_rtf_spans
from scripts.ingest_srd35.extraction_ir import build_extraction_ir
from scripts.ingest_srd35.entry_annotator import annotate_entries
from scripts.ingest_srd35.sectioning import split_sections_from_blocks
from scripts.ingest_srd35.boundary_filter import apply_boundary_filters
from scripts.ingest_srd35.content_types import load_content_types
from scripts.ingest_srd35.pipeline import _compute_processing_hints


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


def _process_fixture_full(path: Path) -> list[dict]:
    """Run a fixture all the way through boundary filter (covers the
    forward_merge_bucket interaction with entry sections)."""
    sections = _process_fixture(path)
    accepted, _decisions = apply_boundary_filters(
        path.stem, path.name, sections, boilerplate_phrases=set(),
    )
    return accepted


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
    """Synthetic split-block fixture: ACROBATIC and [GENERAL] are on separate
    \\par lines so the title/subtitle predicate fires.

    NOTE: real Feats.rtf encodes the title and [TAG] subtitle in the SAME
    \\par (e.g., `\\par ACROBATIC }{\\fs20 [GENERAL]\\par`), which the
    current entry_with_statblock shape does NOT detect — only ~1/150 real
    feats annotate. This synthetic fixture intentionally splits them so
    pipeline integration is testable, but it does NOT prove that real-corpus
    feat detection works yet. Tracked as a known gap; fix path is either
    splitting blocks at intra-paragraph font-size changes in the IR builder
    or extending the shape rule to accept inline subtitle changes.
    """
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


class GapBlocksDoNotPolluteEntrySectionTests(unittest.TestCase):
    """Reviewer-flagged risk: file-opener blocks (e.g., 'SPELLS EXCERPT'
    title) used to be merged-forward and then prepended into the FIRST
    entry section by boundary_filter, polluting the entry's content and
    shifting structure_cuts offsets. Now the bucket is promoted to a
    standalone non-entry section ahead of the entry."""

    def test_first_entry_content_does_not_contain_file_opener(self) -> None:
        sections = _process_fixture_full(FIXTURE_DIR / "SpellsExcerpt.rtf")
        entry_sections = [s for s in sections if "entry_metadata" in s]
        self.assertGreaterEqual(len(entry_sections), 1)
        first = entry_sections[0]
        self.assertEqual(first["entry_metadata"]["entry_title"], "Sanctuary")
        # The opener "SPELLS EXCERPT" must NOT have been prepended.
        self.assertNotIn("SPELLS EXCERPT", first["content"])
        # Sanctuary's own block content is intact.
        self.assertTrue(first["content"].startswith("Sanctuary"))

    def test_first_entry_processing_hints_offset_lands_after_stat_block(self) -> None:
        # The block-derived stat_block_end_char (now stamped on
        # entry_metadata at sectioning time) must point to the end of
        # the spell's stat block, not somewhere shifted by a prepended
        # opener or by description text that happens to look like a
        # field line.
        sections = _process_fixture_full(FIXTURE_DIR / "SpellsExcerpt.rtf")
        first = next(s for s in sections if "entry_metadata" in s)
        meta = first["entry_metadata"]
        hints = _compute_processing_hints(first, meta)
        self.assertIn("structure_cuts", hints)
        cut = hints["structure_cuts"][0]
        # Slice must include the last stat field ("Components: V, S, DF")
        # and exclude the description text that follows.
        sliced = first["content"][:cut["char_offset"]]
        self.assertIn("Components: V, S, DF", sliced)
        self.assertNotIn("Any opponent", sliced)


if __name__ == "__main__":
    unittest.main()
