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

    def test_baseline_tie_break_prefers_larger(self) -> None:
        # Equal counts of fs24 and fs20 (both non-bold). Tie-break to larger.
        spans = _make_block_spans(
            ("a", 24, False), ("\n", 24, False),
            ("b", 24, False), ("\n", 24, False),
            ("c", 20, False), ("\n", 20, False),
            ("d", 20, False), ("\n", 20, False),
        )
        ir = build_extraction_ir(file_name="t.rtf", spans=spans)
        self.assertEqual(ir["document_baseline_font_size"], 24)

    def test_mid_span_newline_preserves_formatting_on_both_sides(self) -> None:
        spans = [TextSpan(text="foo\nbar", font_size=24, bold=True)]
        ir = build_extraction_ir(file_name="t.rtf", spans=spans)
        self.assertEqual(len(ir["blocks"]), 2)
        self.assertEqual(ir["blocks"][0]["text"], "foo")
        self.assertTrue(ir["blocks"][0]["all_bold"])
        self.assertEqual(ir["blocks"][0]["font_size"], 24)
        self.assertEqual(ir["blocks"][1]["text"], "bar")
        self.assertTrue(ir["blocks"][1]["all_bold"])
        self.assertEqual(ir["blocks"][1]["font_size"], 24)

    def test_blank_lines_preserve_source_line_numbers(self) -> None:
        # Codex P2: line_start / line_end must reflect source line numbers,
        # not block sequence numbers. For "a\n\nb", "b" must be at line 3.
        spans = [TextSpan(text="a\n\nb", font_size=24, bold=False)]
        ir = build_extraction_ir(file_name="t.rtf", spans=spans)
        self.assertEqual(len(ir["blocks"]), 2)  # blank line skipped from output
        self.assertEqual(ir["blocks"][0]["text"], "a")
        self.assertEqual(ir["blocks"][0]["line_start"], 1)
        self.assertEqual(ir["blocks"][1]["text"], "b")
        self.assertEqual(ir["blocks"][1]["line_start"], 3)  # NOT 2

    def test_trailing_newline_does_not_emit_extra_blank_block(self) -> None:
        # str.splitlines("foo\n") == ["foo"] — one line, not two.
        spans = [TextSpan(text="foo\n", font_size=24, bold=False)]
        ir = build_extraction_ir(file_name="t.rtf", spans=spans)
        self.assertEqual(len(ir["blocks"]), 1)
        self.assertEqual(ir["blocks"][0]["line_start"], 1)

    def test_whitespace_only_spans_do_not_skew_baseline(self) -> None:
        # Codex P2: previous _summarize_block weighted spaces and tabs as
        # visible chars when computing dominant font_size. A long
        # indentation span at fs20 could push a block's font_size to 20
        # even though all visible content is at fs24, and through that
        # bias the document baseline.
        # Block 1: long indentation at fs20, then short visible text at fs24.
        # Visible-only weighting picks fs24; old behavior picked fs20.
        spans = _make_block_spans(
            ("                    ", 20, False),  # 20 chars of spaces, fs20
            ("text", 24, False),                  # 4 visible chars, fs24
            ("\n", 24, False),
        )
        ir = build_extraction_ir(file_name="t.rtf", spans=spans)
        self.assertEqual(ir["blocks"][0]["font_size"], 24)


class DecodeRtfSpansLinearMergeTests(unittest.TestCase):
    def test_long_same_state_run_does_not_blow_up(self) -> None:
        # Codex P2: avoid O(n²) span merging. Construct a long same-state
        # run via repeated chars and time the decode (sanity check, not a
        # microbenchmark). Mostly we want it to NOT crash / hang.
        from scripts.ingest_srd35.rtf_decoder import decode_rtf_spans
        rtf = r"{\rtf1\ansi " + "x" * 50_000 + r"\par}"
        spans = decode_rtf_spans(rtf)
        joined = "".join(s.text for s in spans)
        self.assertIn("x" * 50_000, joined)
        # Same-state run merges into a single span (plus possibly the \par).
        non_newline_spans = [s for s in spans if s.text.strip()]
        self.assertEqual(len(non_newline_spans), 1)


if __name__ == "__main__":
    unittest.main()
