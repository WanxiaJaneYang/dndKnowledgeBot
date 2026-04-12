"""Tests for retrieval term asset loading."""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts.retrieval.term_assets import TERM_ASSET_ROOT, get_default_term_assets, load_term_assets


class RetrievalTermAssetTests(unittest.TestCase):
    def test_term_asset_files_exist(self) -> None:
        expected = {
            "protected_phrases.json",
            "canonical_aliases.json",
            "surface_variants.json",
            "extraction_candidates.json",
        }
        names = {path.name for path in TERM_ASSET_ROOT.glob("*.json")}
        self.assertTrue(expected.issubset(names), f"Missing term asset files: {expected - names}")

    def test_load_term_assets_returns_expected_shape(self) -> None:
        assets = load_term_assets()

        self.assertEqual(
            set(assets.keys()),
            {
                "protected_phrases",
                "canonical_aliases",
                "surface_variants",
                "extraction_candidates",
            },
        )
        self.assertIsInstance(assets["protected_phrases"], list)
        self.assertIsInstance(assets["canonical_aliases"], dict)
        self.assertIsInstance(assets["surface_variants"], list)
        self.assertIsInstance(assets["extraction_candidates"], list)

    def test_reviewed_runtime_assets_cover_more_than_seed_terms(self) -> None:
        assets = get_default_term_assets()

        self.assertGreaterEqual(len(assets["protected_phrases"]), 25)
        self.assertIn("attack of opportunity", assets["protected_phrases"])
        self.assertIn("spell resistance", assets["protected_phrases"])
        self.assertIn("turn undead", assets["protected_phrases"])
        self.assertIn("hit points", assets["protected_phrases"])

    def test_candidate_pool_is_larger_than_runtime_protected_phrase_list(self) -> None:
        assets = get_default_term_assets()

        self.assertGreater(len(assets["extraction_candidates"]), len(assets["protected_phrases"]))

    def test_term_asset_root_is_repo_relative(self) -> None:
        self.assertTrue(Path(TERM_ASSET_ROOT).is_dir())


if __name__ == "__main__":
    unittest.main()
