from __future__ import annotations

import unittest

from scripts.chunker.config import ChunkerConfig, load_chunker_config


class ChunkerConfigDefaultsTests(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = ChunkerConfig()
        self.assertEqual(cfg.child_threshold_chars, 6000)
        self.assertEqual(cfg.paragraph_group_target_chars, 2000)
        self.assertEqual(cfg.paragraph_group_max_chars, 3000)


class LoadChunkerConfigTests(unittest.TestCase):
    def test_loads_yaml_overrides(self) -> None:
        yaml_text = """\
child_threshold_chars: 4000
paragraph_group_target_chars: 1500
"""
        cfg = load_chunker_config(yaml_text)
        self.assertEqual(cfg.child_threshold_chars, 4000)
        self.assertEqual(cfg.paragraph_group_target_chars, 1500)
        # Unspecified field uses default.
        self.assertEqual(cfg.paragraph_group_max_chars, 3000)

    def test_empty_yaml_returns_defaults(self) -> None:
        cfg = load_chunker_config("")
        self.assertEqual(cfg.child_threshold_chars, 6000)

    def test_yaml_root_must_be_mapping(self) -> None:
        # Codex P2: any truthy non-mapping YAML (a list, a string) used to
        # crash with AttributeError on .items(). Loader now raises ValueError
        # with a helpful message.
        with self.assertRaises(ValueError) as ctx:
            load_chunker_config("- 4000\n- 2000\n")
        self.assertIn("must be a mapping", str(ctx.exception))

    def test_field_value_must_be_int(self) -> None:
        # Codex P2 follow-up: quoted numerics like "4000" used to slip
        # through and cause a downstream TypeError when used in arithmetic.
        with self.assertRaises(ValueError) as ctx:
            load_chunker_config("child_threshold_chars: \"4000\"\n")
        msg = str(ctx.exception)
        self.assertIn("child_threshold_chars", msg)
        self.assertIn("must be int", msg)

    def test_field_value_must_be_positive(self) -> None:
        # Codex P2 follow-up: paragraph_group_max_chars: 0 used to make
        # _enforce_max_chars never progress (infinite loop). Negatives are
        # also nonsensical.
        with self.assertRaises(ValueError) as ctx:
            load_chunker_config("paragraph_group_max_chars: 0\n")
        self.assertIn("must be positive", str(ctx.exception))
        with self.assertRaises(ValueError):
            load_chunker_config("child_threshold_chars: -100\n")

    def test_bool_is_not_accepted_as_int(self) -> None:
        # Python bool is a subclass of int; without the explicit guard
        # `paragraph_group_max_chars: true` would silently become 1 and
        # break paragraph splitting.
        with self.assertRaises(ValueError):
            load_chunker_config("paragraph_group_max_chars: true\n")


if __name__ == "__main__":
    unittest.main()
