import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.fetch_srd_35 import (
    ChecksumMismatchError,
    build_materialization_plan,
    materialize_source,
)


class FetchSrd35Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.source_dir = self.repo_root / "source"
        self.source_dir.mkdir()

        self.archive_path = self.source_dir / "SRD.zip"
        with zipfile.ZipFile(self.archive_path, "w") as archive:
            archive.writestr("Basics.rtf", "{\\rtf1 bootstrap basics}")
            archive.writestr("CombatI.rtf", "{\\rtf1 bootstrap combat}")

        self.archive_sha1 = self._sha1(self.archive_path)

        self.manifest = {
            "source_id": "srd_35",
            "edition": "3.5e",
            "artifact": {
                "filename": "SRD.zip",
                "download_url": self.archive_path.resolve().as_uri(),
                "checksum": {
                    "algorithm": "sha1",
                    "value": self.archive_sha1,
                },
                "expected_file_count": 2,
            },
            "local_layout": {
                "raw_root": "data/raw/srd_35",
                "archive_path": "data/raw/srd_35/SRD.zip",
                "expanded_root": "data/raw/srd_35/rtf",
                "provenance_path": "data/raw/srd_35/bootstrap_provenance.json",
                "extracted_root": "data/extracted/srd_35",
                "canonical_root": "data/canonical/srd_35",
            },
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_build_materialization_plan_reports_expected_paths(self) -> None:
        plan = build_materialization_plan(self.manifest, self.repo_root)

        self.assertEqual(plan["source_id"], "srd_35")
        self.assertEqual(
            plan["archive_path"],
            str((self.repo_root / "data/raw/srd_35/SRD.zip").resolve()),
        )
        self.assertEqual(
            plan["expanded_root"],
            str((self.repo_root / "data/raw/srd_35/rtf").resolve()),
        )
        self.assertEqual(
            plan["provenance_path"],
            str((self.repo_root / "data/raw/srd_35/bootstrap_provenance.json").resolve()),
        )

    def test_materialize_source_downloads_extracts_and_writes_provenance(self) -> None:
        result = materialize_source(self.manifest, self.repo_root)

        raw_root = self.repo_root / "data/raw/srd_35"
        self.assertTrue((raw_root / "SRD.zip").exists())
        self.assertTrue((raw_root / "rtf" / "Basics.rtf").exists())
        self.assertTrue((raw_root / "rtf" / "CombatI.rtf").exists())
        provenance_path = raw_root / "bootstrap_provenance.json"
        self.assertTrue(provenance_path.exists())

        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        self.assertEqual(provenance["source_id"], "srd_35")
        self.assertEqual(provenance["archive"]["verified_checksum"], self.archive_sha1)
        self.assertEqual(provenance["archive"]["extracted_file_count"], 2)
        self.assertEqual(result["archive_checksum"], self.archive_sha1)

    def test_materialize_source_rejects_checksum_mismatch(self) -> None:
        self.manifest["artifact"]["checksum"]["value"] = "0" * 40

        with self.assertRaises(ChecksumMismatchError):
            materialize_source(self.manifest, self.repo_root)

    def test_dry_run_does_not_write_raw_files(self) -> None:
        plan = materialize_source(self.manifest, self.repo_root, dry_run=True)

        self.assertEqual(plan["source_id"], "srd_35")
        self.assertFalse((self.repo_root / "data/raw/srd_35").exists())

    @staticmethod
    def _sha1(path: Path) -> str:
        import hashlib

        digest = hashlib.sha1()
        with path.open("rb") as handle:
            digest.update(handle.read())
        return digest.hexdigest()


if __name__ == "__main__":
    unittest.main()
