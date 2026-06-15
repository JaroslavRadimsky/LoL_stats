from __future__ import annotations

import unittest

from lol_stats.generate import is_top_augment_candidate


class TopAugmentFilterTests(unittest.TestCase):
    def test_excludes_system_arena_choices(self) -> None:
        excluded_names = [
            "Gain a Prismatic Stat Anvil",
            "Level Augments",
            "Replace Augment",
            "Compulsion for Power",
            "  COMPULSION   FOR POWER ",
        ]

        for name in excluded_names:
            with self.subTest(name=name):
                self.assertFalse(is_top_augment_candidate({"name": name}))

    def test_keeps_regular_augment(self) -> None:
        self.assertTrue(is_top_augment_candidate({"name": "Jeweled Gauntlet"}))


if __name__ == "__main__":
    unittest.main()
