from __future__ import annotations

import unittest

from lol_stats.generate import RiotApiClient
from lol_stats.storage import TursoMatchStore


def sample_match(match_id: str = "TEST_1") -> dict:
    return {
        "metadata": {"matchId": match_id},
        "info": {
            "queueId": 1750,
            "gameEndTimestamp": 123,
            "participants": [
                {
                    "puuid": "player-1",
                    "championName": "Talon",
                    "teamId": 100,
                    "win": True,
                    "kills": 5,
                    "deaths": 2,
                    "assists": 7,
                    "playerAugment1": 93,
                    "playerAugment2": 0,
                    "playerAugment3": 124,
                }
            ],
        },
    }


class TursoMatchStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = TursoMatchStore(":memory:", "")

    def tearDown(self) -> None:
        self.store.close()

    def test_saves_raw_match_participant_and_augments(self) -> None:
        match = sample_match()

        self.store.save_match("europe", match)

        self.assertEqual(self.store.get_match("TEST_1"), match)
        self.assertEqual(
            self.store.connection.execute("SELECT COUNT(*) FROM participants").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.store.connection.execute(
                "SELECT COUNT(*) FROM participant_augments"
            ).fetchone()[0],
            2,
        )

    def test_client_uses_stored_match_before_riot_api(self) -> None:
        match = sample_match("TEST_CACHE")
        self.store.save_match("europe", match)
        client = RiotApiClient("unused", match_store=self.store)

        def fail_request(*args, **kwargs):
            raise AssertionError("Riot match detail API should not be called")

        client._request = fail_request

        self.assertEqual(client.get_match("europe", "TEST_CACHE"), match)
        self.assertEqual(self.store.cache_hits, 1)


if __name__ == "__main__":
    unittest.main()
