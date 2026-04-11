import os
import unittest
from pathlib import Path

from scripts.ingest_srd35 import load_golden_outputs, run_fixture_ingestion, write_golden_outputs


class GoldenIngestionTests(unittest.TestCase):
    def test_fixture_ingestion_matches_golden_outputs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        evidence = run_fixture_ingestion(repo_root)

        if os.environ.get("UPDATE_GOLDEN") == "1":
            write_golden_outputs(repo_root, evidence)

        expected = load_golden_outputs(repo_root)
        self.assertEqual(evidence["extracted"], expected["extracted"])
        self.assertEqual(evidence["canonical"], expected["canonical"])


if __name__ == "__main__":
    unittest.main()
