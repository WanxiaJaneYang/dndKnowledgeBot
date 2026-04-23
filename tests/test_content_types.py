from __future__ import annotations

import unittest
from pathlib import Path

from scripts.ingest_srd35.content_types import (
    ContentTypeConfig,
    load_content_types,
    eligible_types_for_file,
)


class LoadContentTypesTests(unittest.TestCase):
    def test_load_yaml(self) -> None:
        yaml_text = """\
content_types:
  - name: spell
    category: Spells
    chunk_type: spell_entry
    shape: entry_with_statblock
    shape_params:
      max_title_len: 80
      max_subtitle_len: 80
      min_fields: 2
      field_pattern: '^[A-Z][\\w]+:'
    file_match: ["Spells*.rtf"]
"""
        types = load_content_types(yaml_text)
        self.assertEqual(len(types), 1)
        spell = types[0]
        self.assertEqual(spell.name, "spell")
        self.assertEqual(spell.category, "Spells")
        self.assertEqual(spell.chunk_type, "spell_entry")
        self.assertEqual(spell.shape, "entry_with_statblock")
        self.assertEqual(spell.shape_params["min_fields"], 2)
        self.assertEqual(spell.file_match, ["Spells*.rtf"])

    def test_no_file_match_means_always_eligible(self) -> None:
        yaml_text = """\
content_types:
  - name: any_entry
    category: Misc
    chunk_type: spell_entry
    shape: definition_list
    shape_params:
      min_blocks: 3
      term_pattern: '^[A-Z]+:'
"""
        types = load_content_types(yaml_text)
        self.assertEqual(types[0].file_match, None)


class EligibleTypesForFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spell = ContentTypeConfig(
            name="spell", category="Spells", chunk_type="spell_entry",
            shape="entry_with_statblock", shape_params={},
            file_match=["Spells*.rtf", "EpicSpells.rtf"],
        )
        self.condition = ContentTypeConfig(
            name="condition", category="Conditions", chunk_type="condition_entry",
            shape="definition_list", shape_params={},
            file_match=["AbilitiesandConditions.rtf"],
        )
        self.always = ContentTypeConfig(
            name="any", category="Misc", chunk_type="spell_entry",
            shape="entry_with_statblock", shape_params={},
            file_match=None,
        )

    def test_glob_match(self) -> None:
        types = [self.spell, self.condition]
        eligible = eligible_types_for_file("SpellsS.rtf", types)
        self.assertEqual([t.name for t in eligible], ["spell"])

    def test_exact_match(self) -> None:
        eligible = eligible_types_for_file(
            "AbilitiesandConditions.rtf",
            [self.spell, self.condition],
        )
        self.assertEqual([t.name for t in eligible], ["condition"])

    def test_no_match(self) -> None:
        eligible = eligible_types_for_file(
            "Description.rtf", [self.spell, self.condition],
        )
        self.assertEqual(eligible, [])

    def test_no_file_match_always_eligible(self) -> None:
        eligible = eligible_types_for_file(
            "Anything.rtf", [self.spell, self.always],
        )
        self.assertEqual([t.name for t in eligible], ["any"])


if __name__ == "__main__":
    unittest.main()
