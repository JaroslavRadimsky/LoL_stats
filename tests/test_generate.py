from __future__ import annotations

import unittest

from lol_stats.generate import collect_mode_matches, is_top_augment_candidate


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


class FakeRiotClient:
    def __init__(self) -> None:
        self.match_id_calls = []
        self.matches = {
            "MATCH_ARENA": {
                "metadata": {"matchId": "MATCH_ARENA"},
                "info": {"queueId": 1750, "gameEndTimestamp": 200},
            },
            "MATCH_MAYHEM": {
                "metadata": {"matchId": "MATCH_MAYHEM"},
                "info": {"queueId": 2400, "gameEndTimestamp": 100},
            },
        }

    def get_match_ids(
        self,
        region: str,
        puuid: str,
        *,
        count: int,
        queue: int | None = None,
        start: int = 0,
    ) -> list[str]:
        self.match_id_calls.append({"count": count, "queue": queue, "start": start})
        if queue == 2400:
            return []
        return ["MATCH_ARENA", "MATCH_MAYHEM"]

    def get_match(self, region: str, match_id: str) -> dict:
        return self.matches[match_id]


class GenerateTests(unittest.TestCase):
    def test_collect_mode_matches_scans_unfiltered_history_when_queue_filter_is_empty(self) -> None:
        client = FakeRiotClient()

        matches = collect_mode_matches(
            client,
            "europe",
            "player-puuid",
            queue_ids=[2400],
            match_count=5,
            history_scan_count=2,
        )

        self.assertEqual([match["metadata"]["matchId"] for match in matches], ["MATCH_MAYHEM"])
        self.assertEqual(
            client.match_id_calls,
            [
                {"count": 5, "queue": 2400, "start": 0},
                {"count": 2, "queue": None, "start": 0},
            ],
        )


if __name__ == "__main__":
    unittest.main()
