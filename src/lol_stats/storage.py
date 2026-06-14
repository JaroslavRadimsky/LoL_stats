from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import libsql


class TursoMatchStore:
    def __init__(self, database_url: str, auth_token: str) -> None:
        self.connection = libsql.connect(database=database_url, auth_token=auth_token)
        self.cache_hits = 0
        self.cache_writes = 0
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS matches (
                match_id TEXT PRIMARY KEY,
                region TEXT NOT NULL,
                queue_id INTEGER,
                game_end_timestamp INTEGER,
                raw_json TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS participants (
                match_id TEXT NOT NULL,
                puuid TEXT NOT NULL,
                champion_name TEXT,
                team_id INTEGER,
                won INTEGER NOT NULL,
                kills INTEGER NOT NULL,
                deaths INTEGER NOT NULL,
                assists INTEGER NOT NULL,
                PRIMARY KEY (match_id, puuid)
            );

            CREATE TABLE IF NOT EXISTS participant_augments (
                match_id TEXT NOT NULL,
                puuid TEXT NOT NULL,
                slot INTEGER NOT NULL,
                augment_id INTEGER NOT NULL,
                PRIMARY KEY (match_id, puuid, slot)
            );

            CREATE INDEX IF NOT EXISTS idx_matches_queue_end
                ON matches(queue_id, game_end_timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_participants_puuid
                ON participants(puuid);
            CREATE INDEX IF NOT EXISTS idx_participant_augments_id
                ON participant_augments(augment_id);
            """
        )
        self.connection.commit()

    def get_match(self, match_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT raw_json FROM matches WHERE match_id = ?",
            (match_id,),
        ).fetchone()
        if not row:
            return None
        self.cache_hits += 1
        return json.loads(row[0])

    def save_match(self, region: str, match: dict[str, Any]) -> None:
        metadata = match.get("metadata", {})
        info = match.get("info", {})
        match_id = metadata.get("matchId")
        if not match_id:
            return

        self.connection.execute(
            """
            INSERT OR IGNORE INTO matches (
                match_id, region, queue_id, game_end_timestamp, raw_json, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                region,
                info.get("queueId"),
                info.get("gameEndTimestamp", 0),
                json.dumps(match, ensure_ascii=False, separators=(",", ":")),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        for participant in info.get("participants", []):
            puuid = participant.get("puuid")
            if not puuid:
                continue
            self.connection.execute(
                """
                INSERT OR IGNORE INTO participants (
                    match_id, puuid, champion_name, team_id, won, kills, deaths, assists
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    puuid,
                    participant.get("championName"),
                    participant.get("teamId"),
                    int(bool(participant.get("win"))),
                    participant.get("kills", 0),
                    participant.get("deaths", 0),
                    participant.get("assists", 0),
                ),
            )

            augments = sorted(
                (
                    int(key.removeprefix("playerAugment")),
                    value,
                )
                for key, value in participant.items()
                if key.startswith("playerAugment")
                and key.removeprefix("playerAugment").isdigit()
                and isinstance(value, int)
                and value > 0
            )
            for slot, augment_id in augments:
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO participant_augments (
                        match_id, puuid, slot, augment_id
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (match_id, puuid, slot, augment_id),
                )

        self.connection.commit()
        self.cache_writes += 1

    def close(self) -> None:
        self.connection.close()
