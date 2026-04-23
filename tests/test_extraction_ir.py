from __future__ import annotations

import unittest

from scripts.ingest_srd35.extraction_ir import build_extraction_ir
from scripts.ingest_srd35.text_spans import TextSpan


def _make_block_spans(*pairs: tuple[str, int, bool]) -> list[TextSpan]:
    return [TextSpan(text=text, font_size=fs, bold=b) for text, fs, b in pairs]


class BuildExtractionIRFromSpansTests(unittest.TestCase):
    def test_single_paragraph_block(self) -> None:
        spans = _make_block_spans(("Hello world.", 24, False), ("\n", 24, False))
        ir = build_extraction_ir(file_name="test.rtf", spans=spans)
        blocks = ir["blocks"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["text"], "Hello world.")
        self.assertEqual(blocks[0]["font_size"], 24)
        self.assertFalse(blocks[0]["starts_with_bold"])
        self.assertFalse(blocks[0]["all_bold"])

    def test_starts_with_bold_first_run(self) -> None:
        spans = _make_block_spans(
            ("Level:", 20, True),
            (" Clr 1", 20, False),
            ("\n", 20, False),
        )
        ir = build_extraction_ir(file_name="t.rtf", spans=spans)
        block = ir["blocks"][0]
        self.assertTrue(block["starts_with_bold"])
        self.assertFalse(block["all_bold"])

    def test_all_bold(self) -> None:
        spans = _make_block_spans(("HEADING", 24, True), ("\n", 24, True))
        block = build_extraction_ir(file_name="t.rtf", spans=spans)["blocks"][0]
        self.assertTrue(block["starts_with_bold"])
        self.assertTrue(block["all_bold"])

    def test_font_size_dominant_by_chars(self) -> None:
        spans = _make_block_spans(
            ("aa", 20, False),       # 2 chars at fs20
            ("bbbbbbbbbb", 24, False),  # 10 chars at fs24
            ("\n", 24, False),
        )
        block = build_extraction_ir(file_name="t.rtf", spans=spans)["blocks"][0]
        self.assertEqual(block["font_size"], 24)

    def test_leading_whitespace_not_counted_for_starts_with_bold(self) -> None:
        spans = _make_block_spans(
            ("   ", 20, False),  # leading whitespace, not bold
            ("Level:", 20, True),
            ("\n", 20, False),
        )
        block = build_extraction_ir(file_name="t.rtf", spans=spans)["blocks"][0]
        self.assertTrue(block["starts_with_bold"])

    def test_document_baseline_stored(self) -> None:
        spans = _make_block_spans(
            ("Body text here", 24, False), ("\n", 24, False),
            ("More body text", 24, False), ("\n", 24, False),
            ("stat", 20, False), ("\n", 20, False),
        )
        ir = build_extraction_ir(file_name="t.rtf", spans=spans)
        self.assertEqual(ir["document_baseline_font_size"], 24)
        self.assertEqual(ir["blocks"][0]["font_size_class"], "body")
        self.assertEqual(ir["blocks"][2]["font_size_class"], "smaller")

    def test_baseline_excludes_bold_blocks(self) -> None:
        # If we counted bold blocks, fs20 (the stat-block size) would
        # tie with fs24. Excluding them, fs24 wins as baseline.
        spans = _make_block_spans(
            ("Title one", 24, False), ("\n", 24, False),
            ("Title two", 24, False), ("\n", 24, False),
            ("Field:", 20, True), (" v", 20, False), ("\n", 20, False),
            ("Field:", 20, True), (" v", 20, False), ("\n", 20, False),
        )
        ir = build_extraction_ir(file_name="t.rtf", spans=spans)
        self.assertEqual(ir["document_baseline_font_size"], 24)


if __name__ == "__main__":
    unittest.main()
