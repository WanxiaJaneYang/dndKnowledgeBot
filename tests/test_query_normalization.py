"""Tests for Phase 1 retrieval query normalization."""
from __future__ import annotations

import unittest

from scripts.retrieval import normalize_query
from scripts.retrieval.term_assets import get_default_term_assets


class QueryNormalizationTests(unittest.TestCase):
    def test_uses_file_backed_term_assets(self) -> None:
        assets = get_default_term_assets()

        self.assertIn("spell resistance", assets["protected_phrases"])
        self.assertIn("attacks of opportunity", assets["surface_variants"])
        self.assertEqual(assets["canonical_aliases"]["hp"], "hit points")

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

    def test_protects_terms_loaded_from_reviewed_assets(self) -> None:
        result = normalize_query("How does spell resistance work?")

        self.assertEqual(result["protected_phrases"], ["spell resistance"])
        self.assertEqual(
            result["tokens"],
            ["how", "does", "spell resistance", "work"],
        )

    def test_expands_bab_alias_and_protects_base_attack_bonus(self) -> None:
        result = normalize_query("fighter bab")

        self.assertEqual(result["normalized_text"], "fighter base attack bonus")
        self.assertEqual(result["tokens"], ["fighter", "base attack bonus"])
        self.assertEqual(
            result["alias_expansions"],
            [{"source": "bab", "target": "base attack bonus"}],
        )
        self.assertEqual(result["protected_phrases"], ["base attack bonus", "attack bonus"])

    def test_expands_dark_vision_alias_to_darkvision(self) -> None:
        result = normalize_query("dark vision")

        self.assertEqual(result["normalized_text"], "darkvision")
        self.assertEqual(result["tokens"], ["darkvision"])
        self.assertEqual(
            result["alias_expansions"],
            [{"source": "dark vision", "target": "darkvision"}],
        )
        self.assertIn("alias_expansion", result["applied_rules"])

    def test_protects_touch_and_flat_footed_ac_terms(self) -> None:
        touch = normalize_query("What is touch armor class?")
        self.assertEqual(touch["protected_phrases"], ["touch armor class", "armor class"])
        self.assertEqual(
            touch["tokens"],
            ["what", "is", "touch armor class"],
        )

        flat_footed = normalize_query("flat-footed armor class")
        self.assertIn("flat footed armor class", flat_footed["protected_phrases"])
        self.assertEqual(flat_footed["normalized_text"], "flat footed armor class")

    def test_reports_lightweight_query_mode(self) -> None:
        result = normalize_query("turn undead")

        self.assertEqual(result["query_mode"], "keyword_lookup")

        natural_language = normalize_query("What is the hit die for a fighter?")
        self.assertEqual(natural_language["query_mode"], "natural_language")


if __name__ == "__main__":
    unittest.main()
