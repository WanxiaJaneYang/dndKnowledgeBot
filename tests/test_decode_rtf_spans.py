from __future__ import annotations

import unittest

from scripts.ingest_srd35.rtf_decoder import decode_rtf_text


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


if __name__ == "__main__":
    unittest.main()
