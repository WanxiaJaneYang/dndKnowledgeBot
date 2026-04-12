"""Tests for Phase 1 retrieval query normalization."""
from __future__ import annotations

import unittest

from scripts.retrieval import normalize_query


class QueryNormalizationTests(unittest.TestCase):
    def test_normalizes_case_whitespace_and_punctuation(self) -> None:
        result = normalize_query("  What ARE   bonus feats?!  ")

        self.assertEqual(result["original_query"], "  What ARE   bonus feats?!  ")
        self.assertEqual(result["normalized_text"], "what are bonus feats")
        self.assertEqual(result["tokens"], ["what", "are", "bonus", "feats"])
        self.assertEqual(result["protected_phrases"], [])
        self.assertEqual(
            result["applied_rules"],
            ["trim_whitespace", "case_fold", "punctuation_cleanup", "whitespace_normalization"],
        )

    def test_expands_high_value_aliases(self) -> None:
        result = normalize_query("fighter hp")

        self.assertEqual(result["normalized_text"], "fighter hit points")
        self.assertEqual(result["tokens"], ["fighter", "hit points"])
        self.assertEqual(
            result["alias_expansions"],
            [{"source": "hp", "target": "hit points"}],
        )
        self.assertIn("alias_expansion", result["applied_rules"])
        self.assertEqual(result["protected_phrases"], ["hit points"])

    def test_keeps_multiword_rules_terms_together(self) -> None:
        result = normalize_query("How does attack of opportunity work?")

        self.assertEqual(result["normalized_text"], "how does attack of opportunity work")
        self.assertEqual(result["protected_phrases"], ["attack of opportunity"])
        self.assertEqual(
            result["tokens"],
            ["how", "does", "attack of opportunity", "work"],
        )

    def test_reports_lightweight_query_mode(self) -> None:
        result = normalize_query("turn undead")

        self.assertEqual(result["query_mode"], "keyword_lookup")

        natural_language = normalize_query("What is the hit die for a fighter?")
        self.assertEqual(natural_language["query_mode"], "natural_language")


if __name__ == "__main__":
    unittest.main()
