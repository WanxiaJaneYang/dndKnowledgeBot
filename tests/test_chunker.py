"""Tests for the baseline chunker pipeline.

Runs against the committed fixture canonical documents so the test suite
requires no live data or network access.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.chunker import (
    chunk_source,
    classify_chunk_type,
    load_golden_chunk_outputs,
    run_fixture_chunking,
    write_golden_chunk_outputs,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_CANONICAL_ROOT = REPO_ROOT / "tests" / "fixtures" / "expected" / "canonical"


class TypeClassifierTests(unittest.TestCase):
    def test_legal_section_is_generic(self) -> None:
        self.assertEqual(classify_chunk_type(["Legal", "Legal Information"]), "generic")

    def test_ogl_section_is_generic(self) -> None:
        self.assertEqual(
            classify_chunk_type(["Legal", "OPEN GAME LICENSE Version 1.0a"]), "generic"
        )

    def test_intro_section_is_rule_section(self) -> None:
        self.assertEqual(classify_chunk_type(["Races", "Races"]), "rule_section")

    def test_ogl_content_overrides_rule_section_path(self) -> None:
        # section_path alone looks like a rule_section intro, but content is OGL boilerplate
        ogl_content = "This material is Open Game Content, and is licensed for public use under the terms of the Open Game License v1.0a."
        self.assertEqual(classify_chunk_type(["Description", "Description"], ogl_content), "generic")

    def test_ogl_prefix_does_not_demote_section_with_substantial_content(self) -> None:
        # section_path looks like rule_section; content starts with OGL line but has real rule text after it
        content = (
            "This material is Open Game Content, and is licensed for public use under the terms of the Open Game License v1.0a.\n"
            "DIVINE MINIONS\nAll types of beings may serve deities."
        )
        self.assertEqual(classify_chunk_type(["DivineMinions", "DivineMinions"], content), "rule_section")

    def test_rule_content_not_demoted_by_incidental_ogl_mention(self) -> None:
        # A rule that merely cites OGL in the middle should not be demoted
        rule_content = "Dwarves have darkvision 60 ft. See Open Game License for reproduction rights."
        self.assertEqual(classify_chunk_type(["Races", "DWARVES"], rule_content), "subsection")

    def test_subsection_is_subsection(self) -> None:
        self.assertEqual(classify_chunk_type(["Races", "DWARVES"]), "subsection")
        self.assertEqual(classify_chunk_type(["Races", "Favored Class"]), "subsection")

    def test_empty_section_path_is_generic(self) -> None:
        self.assertEqual(classify_chunk_type([]), "generic")

    def test_single_element_is_rule_section(self) -> None:
        # Only one element — treat as top-level intro
        self.assertEqual(classify_chunk_type(["Combat"]), "rule_section")


class ChunkPipelineTests(unittest.TestCase):
    def _run_chunker(self, **kwargs) -> tuple[list[dict], dict]:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "chunks"
            result = chunk_source(
                canonical_root=FIXTURE_CANONICAL_ROOT,
                output_root=output_root,
                repo_root=REPO_ROOT,
                source_id="srd_35_fixture",
                **kwargs,
            )
            # Read all chunk files before temp dir is cleaned up.
            chunks = []
            for p in sorted(output_root.glob("*.json")):
                if p.name != "chunk_report.json":
                    chunks.append(json.loads(p.read_text(encoding="utf-8")))
            report = json.loads((output_root / "chunk_report.json").read_text(encoding="utf-8"))
        return chunks, report

    def test_chunk_count_matches_canonical_doc_count(self) -> None:
        canonical_docs = [
            p for p in FIXTURE_CANONICAL_ROOT.glob("*.json")
            if p.name != "canonical_report.json"
        ]
        chunks, report = self._run_chunker()
        self.assertEqual(len(chunks), len(canonical_docs))
        self.assertEqual(report["chunk_count"], len(canonical_docs))

    def test_required_fields_present(self) -> None:
        chunks, _ = self._run_chunker()
        required = {"chunk_id", "document_id", "source_ref", "locator", "chunk_type", "content"}
        for chunk in chunks:
            missing = required - set(chunk.keys())
            self.assertFalse(missing, f"Chunk missing fields: {missing}\n{chunk.get('chunk_id', '<no chunk_id>')}")

    def test_chunk_id_is_stable_and_unique(self) -> None:
        chunks, _ = self._run_chunker()
        ids = [c["chunk_id"] for c in chunks]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate chunk_ids found")
        for cid in ids:
            self.assertTrue(cid.startswith("chunk::"), f"Unexpected chunk_id format: {cid}")

    def test_source_ref_inherited_from_canonical(self) -> None:
        chunks, _ = self._run_chunker()
        for chunk in chunks:
            self.assertEqual(chunk["source_ref"]["source_id"], "srd_35_fixture")
            self.assertEqual(chunk["source_ref"]["edition"], "3.5e")

    def test_adjacency_links_are_consistent(self) -> None:
        chunks, _ = self._run_chunker()
        id_to_chunk = {c["chunk_id"]: c for c in chunks}
        for chunk in chunks:
            if "previous_chunk_id" in chunk:
                prev = id_to_chunk[chunk["previous_chunk_id"]]
                self.assertEqual(prev.get("next_chunk_id"), chunk["chunk_id"])
            if "next_chunk_id" in chunk:
                nxt = id_to_chunk[chunk["next_chunk_id"]]
                self.assertEqual(nxt.get("previous_chunk_id"), chunk["chunk_id"])

    def test_adjacency_never_crosses_source_files(self) -> None:
        chunks, _ = self._run_chunker()
        id_to_chunk = {c["chunk_id"]: c for c in chunks}

        def source_file(chunk: dict) -> str:
            loc = chunk.get("source_location", "")
            if not loc:
                loc = chunk["locator"].get("source_location", "")
            return loc.split("#")[0] if loc else chunk["locator"].get("section_path", [""])[0]

        for chunk in chunks:
            chunk_file = source_file(chunk)
            if "previous_chunk_id" in chunk:
                prev = id_to_chunk[chunk["previous_chunk_id"]]
                self.assertEqual(
                    source_file(prev), chunk_file,
                    f"previous_chunk_id crosses source files: {chunk['chunk_id']} -> {chunk['previous_chunk_id']}",
                )
            if "next_chunk_id" in chunk:
                nxt = id_to_chunk[chunk["next_chunk_id"]]
                self.assertEqual(
                    source_file(nxt), chunk_file,
                    f"next_chunk_id crosses source files: {chunk['chunk_id']} -> {chunk['next_chunk_id']}",
                )

    def test_first_and_last_per_file_have_no_cross_links(self) -> None:
        chunks, _ = self._run_chunker()
        # Group by source file.
        by_file: dict[str, list[dict]] = {}
        for chunk in chunks:
            loc = chunk["locator"].get("source_location", "")
            key = loc.split("#")[0] if loc else chunk["locator"].get("section_path", [""])[0]
            by_file.setdefault(key, []).append(chunk)
        for file_key, file_chunks in by_file.items():
            self.assertNotIn(
                "previous_chunk_id", file_chunks[0],
                f"First chunk in {file_key} should have no previous_chunk_id",
            )
            self.assertNotIn(
                "next_chunk_id", file_chunks[-1],
                f"Last chunk in {file_key} should have no next_chunk_id",
            )

    def test_first_chunk_has_no_previous(self) -> None:
        chunks, _ = self._run_chunker()
        first = chunks[0]
        self.assertNotIn("previous_chunk_id", first)

    def test_last_chunk_has_no_next(self) -> None:
        chunks, _ = self._run_chunker()
        last = chunks[-1]
        self.assertNotIn("next_chunk_id", last)

    def test_chunk_type_values_are_valid(self) -> None:
        valid_types = {
            "rule_section", "subsection", "spell_entry", "feat_entry",
            "skill_entry", "class_feature", "condition_entry", "glossary_entry",
            "table", "example", "sidebar", "errata_note", "faq_note",
            "paragraph_group", "generic",
        }
        chunks, _ = self._run_chunker()
        for chunk in chunks:
            self.assertIn(chunk["chunk_type"], valid_types)

    def test_content_is_non_empty(self) -> None:
        chunks, _ = self._run_chunker()
        for chunk in chunks:
            self.assertTrue(chunk["content"].strip(), f"Empty content in {chunk['chunk_id']}")

    def test_force_flag_overwrites_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "chunks"
            chunk_source(
                canonical_root=FIXTURE_CANONICAL_ROOT,
                output_root=output_root,
                repo_root=REPO_ROOT,
                source_id="srd_35_fixture",
            )
            # Second run without force should fail.
            with self.assertRaises(FileExistsError):
                chunk_source(
                    canonical_root=FIXTURE_CANONICAL_ROOT,
                    output_root=output_root,
                    repo_root=REPO_ROOT,
                    source_id="srd_35_fixture",
                )
            # Third run with force should succeed.
            chunk_source(
                canonical_root=FIXTURE_CANONICAL_ROOT,
                output_root=output_root,
                repo_root=REPO_ROOT,
                source_id="srd_35_fixture",
                force=True,
            )

    def test_report_contains_expected_fields(self) -> None:
        _, report = self._run_chunker()
        for field in ("source_id", "chunked_at_utc", "strategy", "chunk_count", "records"):
            self.assertIn(field, report)
        self.assertEqual(report["source_id"], "srd_35_fixture")
        self.assertEqual(report["strategy"], "v1-section-passthrough")

    def test_dwarves_chunk_is_subsection(self) -> None:
        chunks, _ = self._run_chunker()
        dwarves = next(
            (c for c in chunks if "dwarves" in c["chunk_id"]), None
        )
        self.assertIsNotNone(dwarves, "No dwarves chunk found")
        self.assertEqual(dwarves["chunk_type"], "subsection")

    def test_legal_chunk_is_generic(self) -> None:
        chunks, _ = self._run_chunker()
        legal = next(
            (c for c in chunks if "legal" in c["chunk_id"].lower()), None
        )
        self.assertIsNotNone(legal, "No legal chunk found")
        self.assertEqual(legal["chunk_type"], "generic")


class GoldenChunkTests(unittest.TestCase):
    def test_fixture_chunking_matches_golden_outputs(self) -> None:
        evidence = run_fixture_chunking(REPO_ROOT)

        if os.environ.get("UPDATE_GOLDEN") == "1":
            write_golden_chunk_outputs(REPO_ROOT, evidence)

        expected = load_golden_chunk_outputs(REPO_ROOT)
        self.assertEqual(evidence["chunks"], expected["chunks"])


if __name__ == "__main__":
    unittest.main()
