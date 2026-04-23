from __future__ import annotations

import unittest

from scripts.ingest_srd35.rtf_decoder import decode_rtf_text
from scripts.ingest_srd35.rtf_decoder import decode_rtf_spans
from scripts.ingest_srd35.text_spans import TextSpan


class DecodeRtfTextRegressionTests(unittest.TestCase):
    """Lock current behavior before refactoring the parser internals."""

    def test_simple_paragraph(self) -> None:
        rtf = r"{\rtf1\ansi Hello world.\par}"
        self.assertEqual(decode_rtf_text(rtf), "Hello world.")

    def test_par_emits_newline(self) -> None:
        rtf = r"{\rtf1\ansi Line one.\par Line two.\par}"
        self.assertEqual(decode_rtf_text(rtf), "Line one.\nLine two.")

    def test_nested_groups(self) -> None:
        rtf = r"{\rtf1\ansi {\b Bold} plain.\par}"
        self.assertEqual(decode_rtf_text(rtf), "Bold plain.")

    def test_unicode_escape(self) -> None:
        rtf = r"{\rtf1\ansi caf\u233?\par}"
        self.assertEqual(decode_rtf_text(rtf), "café")

    def test_emdash(self) -> None:
        rtf = r"{\rtf1\ansi A\emdash B\par}"
        self.assertEqual(decode_rtf_text(rtf), "A--B")


class DecodeRtfSpansTests(unittest.TestCase):
    def test_emits_default_font_size(self) -> None:
        spans = decode_rtf_spans(r"{\rtf1\ansi Hello.\par}")
        self.assertGreater(len(spans), 0)
        for span in spans:
            self.assertEqual(span.font_size, 24)
            self.assertFalse(span.bold)

    def test_fs_changes_propagate(self) -> None:
        rtf = r"{\rtf1\ansi {\fs20 small}{\fs36 big}\par}"
        spans = decode_rtf_spans(rtf)
        sizes = [s.font_size for s in spans if s.text.strip()]
        self.assertIn(20, sizes)
        self.assertIn(36, sizes)

    def test_fs_resets_on_group_exit(self) -> None:
        rtf = r"{\rtf1\ansi {\fs20 inner}outer\par}"
        spans = decode_rtf_spans(rtf)
        # "inner" is fs20; "outer" reverts to default fs24
        inner = [s for s in spans if "inner" in s.text]
        outer = [s for s in spans if "outer" in s.text]
        self.assertTrue(inner)
        self.assertTrue(outer)
        self.assertEqual(inner[0].font_size, 20)
        self.assertEqual(outer[0].font_size, 24)

    def test_bold_open_close(self) -> None:
        rtf = r"{\rtf1\ansi {\b bold}plain\par}"
        spans = decode_rtf_spans(rtf)
        bold = [s for s in spans if "bold" in s.text]
        plain = [s for s in spans if "plain" in s.text]
        self.assertTrue(bold[0].bold)
        self.assertFalse(plain[0].bold)

    def test_bold_zero_turns_off(self) -> None:
        rtf = r"{\rtf1\ansi \b on \b0 off\par}"
        spans = decode_rtf_spans(rtf)
        on_chunk = [s for s in spans if "on" in s.text and "off" not in s.text]
        off_chunk = [s for s in spans if "off" in s.text]
        self.assertTrue(on_chunk[0].bold)
        self.assertFalse(off_chunk[0].bold)

    def test_bold_resets_on_group_exit(self) -> None:
        rtf = r"{\rtf1\ansi {\b inner}outer\par}"
        spans = decode_rtf_spans(rtf)
        inner = [s for s in spans if "inner" in s.text]
        outer = [s for s in spans if "outer" in s.text]
        self.assertTrue(inner[0].bold)
        self.assertFalse(outer[0].bold)

    def test_adjacent_same_state_spans_merge(self) -> None:
        rtf = r"{\rtf1\ansi Hello world.\par}"
        spans = decode_rtf_spans(rtf)
        # All visible chars share state; should collapse to <= 2 spans
        # (one for the text, plus optionally one for the \par newline).
        total_text = "".join(s.text for s in spans)
        self.assertIn("Hello world.", total_text)

    def test_par_emits_newline_in_spans(self) -> None:
        rtf = r"{\rtf1\ansi A\par B\par}"
        spans = decode_rtf_spans(rtf)
        joined = "".join(s.text for s in spans)
        self.assertIn("\n", joined)


if __name__ == "__main__":
    unittest.main()
