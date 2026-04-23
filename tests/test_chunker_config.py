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


if __name__ == "__main__":
    unittest.main()
