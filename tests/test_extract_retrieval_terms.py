"""Tests for SRD retrieval term extraction."""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts.extract_retrieval_terms import extract_term_candidates

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = REPO_ROOT / "data" / "canonical" / "srd_35"
CHUNK_ROOT = REPO_ROOT / "data" / "chunks" / "srd_35"


class ExtractRetrievalTermsTests(unittest.TestCase):
    def test_extract_term_candidates_returns_expected_buckets(self) -> None:
        result = extract_term_candidates(CANONICAL_ROOT, CHUNK_ROOT)

        self.assertEqual(
            set(result.keys()),
            {
                "protected_phrase_candidates",
                "section_title_candidates",
                "content_phrase_candidates",
            },
        )

    def test_extract_term_candidates_finds_obvious_srd_terms(self) -> None:
        result = extract_term_candidates(CANONICAL_ROOT, CHUNK_ROOT)

        protected = set(result["protected_phrase_candidates"])
        self.assertIn("attack of opportunity", protected)
        self.assertIn("spell resistance", protected)
        self.assertIn("turn undead", protected)

    def test_extract_term_candidates_avoids_ogl_noise(self) -> None:
        result = extract_term_candidates(CANONICAL_ROOT, CHUNK_ROOT)
        protected = set(result["protected_phrase_candidates"])

        self.assertNotIn("open game license", protected)
        self.assertNotIn("terms of use", protected)


if __name__ == "__main__":
    unittest.main()
