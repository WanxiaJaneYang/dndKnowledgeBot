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

    def test_decode_rtf_text_skips_ignorable_destination_groups(self) -> None:
        decoded = decode_rtf_text(
            "{\\rtf1\\ansi{\\fonttbl{\\f0 Times New Roman;}}{\\colortbl;\\red0\\green0\\blue0;}"
            "\\b Real Content\\b0\\par Rule text}"
        )
        self.assertEqual(decoded, "Real Content\nRule text")
        self.assertNotIn("Times New Roman", decoded)

    def test_decode_rtf_text_consumes_unicode_fallback_hex(self) -> None:
        decoded = decode_rtf_text("{\\rtf1\\ansi\\uc1 dash:\\u8211\\'97 done}")
        self.assertEqual(decoded, "dash:– done")

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
        self.assertNotIn("ingestion_notes", extraction_report["records"][0])
        self.assertNotIn("extraction_caveats", extraction_report["records"][0])
        self.assertIn("schema_validation", result)
        self.assertFalse(result["schema_validation"]["enabled"])

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

    def test_ingest_source_splits_by_section_headings(self) -> None:
        (self.repo_root / "data/raw/srd_35/rtf/CombatI.rtf").write_text(
            "{\\rtf1\\ansi\\b Full Attack\\b0\\par First section text.\\par\\b Charge\\b0\\par Second section text.}",
            encoding="latin-1",
        )
        result = ingest_source(self.manifest, self.repo_root, force=True)
        self.assertEqual(result["documents_written"], 3)

        canonical_report = json.loads(Path(result["canonical_report"]).read_text(encoding="utf-8"))
        locations = [record["source_location"] for record in canonical_report["records"]]
        self.assertTrue(any("#001_full_attack" in loc for loc in locations))
        self.assertTrue(any("#002_charge" in loc for loc in locations))

    def test_ingest_source_rejects_non_positive_limit(self) -> None:
        with self.assertRaises(ValueError):
            ingest_source(self.manifest, self.repo_root, limit=0)

    def test_ingest_source_requires_force_if_outputs_exist(self) -> None:
        ingest_source(self.manifest, self.repo_root)
        with self.assertRaises(FileExistsError):
            ingest_source(self.manifest, self.repo_root)

    def test_ingest_source_can_require_schema_validation(self) -> None:
        with self.assertRaises(RuntimeError):
            ingest_source(self.manifest, self.repo_root, require_schema_validation=True)


if __name__ == "__main__":
    unittest.main()
