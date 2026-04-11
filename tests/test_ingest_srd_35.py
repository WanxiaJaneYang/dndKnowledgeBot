import json
import tempfile
import unittest
from pathlib import Path

from scripts.ingest_srd_35 import decode_rtf_text, ingest_source


class IngestSrd35Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        (self.repo_root / "data/raw/srd_35/rtf").mkdir(parents=True, exist_ok=True)

        self.manifest = {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
            "local_layout": {
                "raw_root": "data/raw/srd_35",
                "expanded_root": "data/raw/srd_35/rtf",
                "extracted_root": "data/extracted/srd_35",
                "canonical_root": "data/canonical/srd_35",
            },
        }

        (self.repo_root / "data/raw/srd_35/rtf/CombatI.rtf").write_text(
            "{\\rtf1\\ansi\\b Full Attack\\b0\\par You can make more than one attack.}",
            encoding="latin-1",
        )
        (self.repo_root / "data/raw/srd_35/rtf/AbilitiesandConditions.rtf").write_text(
            "{\\rtf1\\ansi\\b Flat-Footed\\b0\\par A flat-footed character cannot make attacks of opportunity.}",
            encoding="latin-1",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_decode_rtf_text_strips_basic_controls(self) -> None:
        decoded = decode_rtf_text("{\\rtf1\\ansi\\b Hello\\b0\\par World}")
        self.assertEqual(decoded, "Hello\nWorld")

    def test_ingest_source_writes_extracted_and_canonical_outputs(self) -> None:
        result = ingest_source(self.manifest, self.repo_root)

        self.assertEqual(result["documents_written"], 2)
        extracted_report_path = Path(result["extraction_report"])
        canonical_report_path = Path(result["canonical_report"])
        self.assertTrue(extracted_report_path.exists())
        self.assertTrue(canonical_report_path.exists())

        extraction_report = json.loads(extracted_report_path.read_text(encoding="utf-8"))
        canonical_report = json.loads(canonical_report_path.read_text(encoding="utf-8"))
        self.assertEqual(len(extraction_report["records"]), 2)
        self.assertEqual(canonical_report["canonical_count"], 2)
        self.assertIn("ingestion_notes", extraction_report)
        self.assertIn("extraction_caveats", extraction_report)

        for record in canonical_report["records"]:
            canonical_path = self.repo_root / record["canonical_path"]
            self.assertTrue(canonical_path.exists())
            payload = json.loads(canonical_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["source_ref"]["source_id"], "srd_35")
            self.assertIn("section_path", payload["locator"])
            self.assertIn("source_location", payload["locator"])
            self.assertIn("source_checksum", payload)
            self.assertIn("ingested_at", payload)
            self.assertTrue(payload["content"])

    def test_ingest_source_limit_only_processes_n_files(self) -> None:
        result = ingest_source(self.manifest, self.repo_root, limit=1, force=True)
        self.assertEqual(result["documents_written"], 1)


if __name__ == "__main__":
    unittest.main()
