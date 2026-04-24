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
        required = {"chunk_id", "document_id", "source_ref", "locator", "chunk_type", "content", "chunk_version"}
        for chunk in chunks:
            missing = required - set(chunk.keys())
            self.assertFalse(missing, f"Chunk missing fields: {missing}\n{chunk.get('chunk_id', '<missing>')}")

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

    def test_chunk_type_values_are_valid(self) -> None:
        valid_types = {
            "rule_section", "subsection", "spell_entry", "feat_entry",
            "skill_entry", "class_feature", "condition_entry", "glossary_entry",
            "stat_block", "table", "example", "sidebar", "errata_note", "faq_note",
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

    def test_nonexistent_canonical_root_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                chunk_source(
                    canonical_root=Path(tmp) / "does_not_exist",
                    output_root=Path(tmp) / "chunks",
                    repo_root=REPO_ROOT,
                )

    def test_source_id_none_derives_from_canonical_docs(self) -> None:
        # When source_id=None the pipeline should derive it from the canonical docs.
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "chunks"
            chunk_source(
                canonical_root=FIXTURE_CANONICAL_ROOT,
                output_root=output_root,
                repo_root=REPO_ROOT,
                source_id=None,
            )
            report = json.loads((output_root / "chunk_report.json").read_text(encoding="utf-8"))
            chunks = [
                json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(output_root.glob("*.json"))
                if p.name != "chunk_report.json"
            ]
        self.assertEqual(report["source_id"], "srd_35_fixture")
        for chunk in chunks:
            self.assertEqual(chunk["source_ref"]["source_id"], report["source_id"])

    def test_source_id_mismatch_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                chunk_source(
                    canonical_root=FIXTURE_CANONICAL_ROOT,
                    output_root=Path(tmp) / "chunks",
                    repo_root=REPO_ROOT,
                    source_id="wrong_source_id",
                )

    def test_report_contains_expected_fields(self) -> None:
        _, report = self._run_chunker()
        for field in ("source_id", "chunked_at_utc", "strategy", "chunk_count", "records", "schema_validation"):
            self.assertIn(field, report)
        self.assertEqual(report["source_id"], "srd_35_fixture")
        self.assertEqual(report["strategy"], "v2-formatting-aware")
        self.assertIn("enabled", report["schema_validation"])

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


class ChunkSchemaTests(unittest.TestCase):
    def test_stat_block_chunk_validates_in_schema(self) -> None:
        import json
        import jsonschema
        repo_root = Path(__file__).resolve().parent.parent
        schema = json.loads((repo_root / "schemas" / "chunk.schema.json").read_text(encoding="utf-8"))
        common = json.loads((repo_root / "schemas" / "common.schema.json").read_text(encoding="utf-8"))
        resolver = jsonschema.RefResolver.from_schema(schema, store={
            "common.schema.json": common, "./common.schema.json": common,
        })
        chunk = {
            "chunk_id": "chunk::srd_35::spells::sanctuary::child_001",
            "document_id": "srd_35::spells::sanctuary",
            "source_ref": {
                "source_id": "srd_35", "title": "SRD", "edition": "3.5e",
                "source_type": "srd", "authority_level": "official_reference",
            },
            "locator": {
                "section_path": ["Spells", "Sanctuary"],
                "source_location": "SpellsS.rtf#001_sanctuary",
            },
            "chunk_type": "stat_block",
            "content": "Level: Clr 1\nComponents: V, S, DF",
            "parent_chunk_id": "chunk::srd_35::spells::sanctuary",
            "split_origin": "structure_cut",
        }
        jsonschema.validate(chunk, schema, resolver=resolver)


class GoldenChunkTests(unittest.TestCase):
    def test_fixture_chunking_matches_golden_outputs(self) -> None:
        evidence = run_fixture_chunking(REPO_ROOT)

        if os.environ.get("UPDATE_GOLDEN") == "1":
            write_golden_chunk_outputs(REPO_ROOT, evidence)

        expected = load_golden_chunk_outputs(REPO_ROOT)
        self.assertEqual(evidence["chunks"], expected["chunks"])


class HierarchyWithStructureCutsTests(unittest.TestCase):
    def _make_canonical_doc(
        self, document_id: str, content: str,
        *, processing_hints: dict | None = None,
        section_path: list[str] | None = None,
    ) -> dict:
        doc = {
            "document_id": document_id,
            "source_ref": {
                "source_id": "srd_35", "title": "SRD", "edition": "3.5e",
                "source_type": "srd", "authority_level": "official_reference",
            },
            "locator": {
                "section_path": section_path or ["Spells", document_id.split("::")[-1]],
                "source_location": f"SpellsS.rtf#001_{document_id.split('::')[-1]}",
            },
            "content": content,
        }
        if processing_hints is not None:
            doc["processing_hints"] = processing_hints
        return doc

    def _run(self, docs: list[dict]) -> list[dict]:
        with tempfile.TemporaryDirectory() as tmp:
            canonical_root = Path(tmp) / "canonical"
            canonical_root.mkdir()
            for i, doc in enumerate(docs):
                (canonical_root / f"doc_{i:03d}.json").write_text(
                    json.dumps(doc, indent=2), encoding="utf-8",
                )
            output_root = Path(tmp) / "chunks"
            chunk_source(
                canonical_root=canonical_root,
                output_root=output_root,
                repo_root=REPO_ROOT,
                source_id="srd_35",
            )
            return [
                json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(output_root.glob("*.json"))
                if p.name != "chunk_report.json"
            ]

    def test_small_doc_no_split(self) -> None:
        doc = self._make_canonical_doc(
            "srd_35::spells::sanctuary",
            "Sanctuary\nAbjuration\nLevel: Clr 1\n\nDescription.",
            processing_hints={"chunk_type_hint": "spell_entry"},
        )
        chunks = self._run([doc])
        self.assertEqual(len(chunks), 1)
        self.assertNotIn("parent_chunk_id", chunks[0])
        self.assertEqual(chunks[0]["chunk_type"], "spell_entry")

    def test_large_doc_with_structure_cut_produces_typed_child(self) -> None:
        # Build content > CHILD_THRESHOLD (6000) with explicit cut at offset = stat block end.
        stat_block = "Sanctuary\nAbjuration\nLevel: Clr 1\nComponents: V, S, DF\nCasting Time: 1 std\nRange: Touch\nTarget: Creature\nDuration: 1 round/level\nSaving Throw: Will negates\nSpell Resistance: No"
        description = "\n\n" + ("A long description " * 600)
        content = stat_block + description
        cut_offset = len(stat_block)
        doc = self._make_canonical_doc(
            "srd_35::spells::big_sanctuary", content,
            processing_hints={
                "chunk_type_hint": "spell_entry",
                "structure_cuts": [{
                    "kind": "stat_block_end",
                    "char_offset": cut_offset,
                    "child_chunk_type": "stat_block",
                }],
            },
        )
        chunks = self._run([doc])
        parents = [c for c in chunks if "parent_chunk_id" not in c]
        children = [c for c in chunks if "parent_chunk_id" in c]
        self.assertEqual(len(parents), 1)
        self.assertGreater(len(children), 0)
        self.assertEqual(parents[0]["chunk_type"], "spell_entry")
        # First child is the stat_block.
        first_child = children[0]
        self.assertEqual(first_child["chunk_type"], "stat_block")
        self.assertEqual(first_child["split_origin"], "structure_cut")
        self.assertIn("Level: Clr 1", first_child["content"])
        # Subsequent children are paragraph_group.
        for child in children[1:]:
            self.assertEqual(child["chunk_type"], "paragraph_group")
            self.assertEqual(child["split_origin"], "paragraph_group")

    def test_char_offset_round_trip(self) -> None:
        stat_block = "Sanctuary\nAbjuration\nLevel: Clr 1"
        description = "\n\n" + ("Description text. " * 500)
        content = stat_block + description
        cut_offset = len(stat_block)
        doc = self._make_canonical_doc(
            "srd_35::spells::roundtrip", content,
            processing_hints={
                "chunk_type_hint": "spell_entry",
                "structure_cuts": [{
                    "kind": "stat_block_end",
                    "char_offset": cut_offset,
                    "child_chunk_type": "stat_block",
                }],
            },
        )
        chunks = self._run([doc])
        children = [c for c in chunks if "parent_chunk_id" in c]
        first_child_content = children[0]["content"]
        # Reconstruct expected: content[0:cut_offset], with only newline trim.
        expected = content[:cut_offset].lstrip("\n").rstrip("\n")
        self.assertEqual(first_child_content, expected)

    def test_paragraph_group_max_chars_enforced_on_runaway_paragraph(self) -> None:
        # Codex P2: a single very long paragraph used to be emitted as one
        # oversized paragraph_group child because grouping only checked the
        # target threshold, never the max cap. Now max_chars is enforced as
        # a hard cap by slicing.
        # One huge paragraph (no \n\n inside) above max threshold.
        runaway = "x" * 9000  # one paragraph of 9000 chars, default max=3000
        # Wrap in an entry so the chunker actually splits it.
        stat_block = "Header\nLine: a"
        content = stat_block + "\n\n" + runaway
        cut_offset = len(stat_block)
        doc = self._make_canonical_doc(
            "srd_35::spells::runaway", content,
            processing_hints={
                "chunk_type_hint": "spell_entry",
                "structure_cuts": [{
                    "kind": "stat_block_end",
                    "char_offset": cut_offset,
                    "child_chunk_type": "stat_block",
                }],
            },
        )
        chunks = self._run([doc])
        pg_children = [c for c in chunks if c.get("split_origin") == "paragraph_group"]
        self.assertGreater(len(pg_children), 1)  # split, not one giant child
        for child in pg_children:
            self.assertLessEqual(len(child["content"]), 3000)  # default max_chars


class EnforceMaxCharsTests(unittest.TestCase):
    """Direct coverage for the _enforce_max_chars helper (Codex round-3 P2 fixes)."""

    def test_sentence_cut_keeps_period_in_prior_chunk(self) -> None:
        # Codex P2: rfind(". ") used to put the period at the START of the
        # next chunk (e.g., next child began with ".") because cut was at
        # the period's index but the slice excluded it. Now period stays
        # in the prior chunk and the trailing space is consumed.
        from scripts.chunker.pipeline import _enforce_max_chars
        # 60-char chunks with one sentence-end at position 30.
        text = ("a" * 30) + ". " + ("b" * 30)
        slices = _enforce_max_chars(text, max_chars=40)
        self.assertEqual(len(slices), 2)
        self.assertTrue(slices[0].endswith("."), f"prior chunk should end with period: {slices[0]!r}")
        self.assertFalse(slices[1].startswith("."), f"next chunk should not start with period: {slices[1]!r}")
        # Reconstructed concatenation is text minus the consumed " " separator.
        self.assertEqual(slices[0] + slices[1], text.replace(". ", "."))

    def test_preserves_internal_whitespace_at_chunk_boundary(self) -> None:
        # Codex P2: previous .strip() stripped spaces and tabs from chunk
        # boundaries, silently destroying meaningful indentation. Now only
        # newline separators are stripped.
        from scripts.chunker.pipeline import _enforce_max_chars
        # Two paragraphs where the second starts with leading spaces (e.g.,
        # an indented quoted block). Chunk boundary at \n\n must NOT eat
        # those spaces. Text length 87 > max=80 so a split is forced.
        text = ("a" * 60) + "\n\n" + "    indented continuation"
        slices = _enforce_max_chars(text, max_chars=80)
        self.assertEqual(len(slices), 2)
        self.assertTrue(
            slices[1].startswith("    "),
            f"chunk-boundary leading spaces lost: {slices[1][:20]!r}",
        )

    def test_paragraph_boundary_separator_consumed(self) -> None:
        from scripts.chunker.pipeline import _enforce_max_chars
        text = ("a" * 50) + "\n\n" + ("b" * 50)
        slices = _enforce_max_chars(text, max_chars=60)
        self.assertEqual(slices, ["a" * 50, "b" * 50])

    def test_raw_char_boundary_when_no_separator(self) -> None:
        from scripts.chunker.pipeline import _enforce_max_chars
        text = "x" * 100
        slices = _enforce_max_chars(text, max_chars=40)
        # Slices fall on raw char boundary; no separator consumed.
        self.assertEqual("".join(slices), text)
        for s in slices:
            self.assertLessEqual(len(s), 40)


if __name__ == "__main__":
    unittest.main()
