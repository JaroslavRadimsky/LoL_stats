from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from .storage import TursoMatchStore

PLATFORM_TO_REGION = {
    "br1": "americas",
    "eun1": "europe",
    "euw1": "europe",
    "jp1": "asia",
    "kr": "asia",
    "la1": "americas",
    "la2": "americas",
    "na1": "americas",
    "oc1": "sea",
    "ph2": "sea",
    "ru": "europe",
    "sg2": "sea",
    "th2": "sea",
    "tr1": "europe",
    "tw2": "sea",
    "vn2": "sea",
}

MODE_QUEUES = {
    "aram": [2400],
    "arena": [1750],
}

MODE_LABELS = {
    "aram": "ARAM: Mayhem",
    "arena": "Arena 3v3",
}

COMMUNITY_DRAGON_ARENA_URL = "https://raw.communitydragon.org/latest/cdragon/arena/en_us.json"
COMMUNITY_DRAGON_ASSET_BASE = (
    "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default"
)
ENCHANTER_CHAMPIONS = {
    "Ivern",
    "Janna",
    "Karma",
    "Lulu",
    "Milio",
    "Nami",
    "Renata",
    "Renata Glasc",
    "Seraphine",
    "Sona",
    "Soraka",
    "Yuumi",
    "Zilean",
}
EXCLUDED_TOP_AUGMENT_NAMES = {
    "compulsion for power",
    "gain a prismatic stat anvil",
    "level augments",
    "replace augment",
}
MATCHLIST_PAGE_SIZE = 100


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def round_stat(value: float, digits: int = 2) -> float:
    return round(value, digits)


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    players = config.get("players", [])
    if not players:
        raise ValueError("Config must contain at least one player in 'players'.")

    for player in players:
        missing = [key for key in ("display_name", "game_name", "tag_line", "platform") if not player.get(key)]
        if missing:
            raise ValueError(f"Player entry is missing required keys: {', '.join(missing)}")
        platform = player["platform"].lower()
        if platform not in PLATFORM_TO_REGION:
            raise ValueError(f"Unsupported platform '{platform}'.")
        if "<" in player["game_name"] or player["game_name"].startswith("Moje"):
            raise ValueError("Replace placeholder Riot IDs in config/players.json before generating live data.")
        player["platform"] = platform

    config["title"] = config.get("title", "LoL Stats Dashboard")
    config["match_count"] = int(config.get("match_count", 100))
    if config["match_count"] <= 0:
        raise ValueError("'match_count' must be a positive integer.")
    config["history_scan_count"] = int(config.get("history_scan_count", min(config["match_count"], 20)))
    if config["history_scan_count"] <= 0:
        raise ValueError("'history_scan_count' must be a positive integer.")
    return config


class RiotApiClient:
    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        match_store: TursoMatchStore | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.session.headers.update({"X-Riot-Token": api_key})
        self._match_cache: dict[str, dict[str, Any]] = {}
        self._ddragon_version: str | None = None
        self.match_store = match_store

    def _request(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        attempts = 0
        while attempts < 4:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "1"))
                time.sleep(retry_after)
                attempts += 1
                continue
            if 500 <= response.status_code < 600:
                time.sleep(1 + attempts)
                attempts += 1
                continue
            response.raise_for_status()
            return response.json()
        response.raise_for_status()
        return {}

    def get_latest_ddragon_version(self) -> str:
        if self._ddragon_version:
            return self._ddragon_version
        versions = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=30)
        versions.raise_for_status()
        self._ddragon_version = versions.json()[0]
        return self._ddragon_version

    def get_account_by_riot_id(self, region: str, game_name: str, tag_line: str) -> dict[str, Any]:
        url = f"https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        return self._request(url)

    def get_summoner_by_puuid(self, platform: str, puuid: str) -> dict[str, Any]:
        url = f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
        return self._request(url)

    def get_match_ids(
        self,
        region: str,
        puuid: str,
        *,
        count: int,
        queue: int | None = None,
        start: int = 0,
    ) -> list[str]:
        url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        params: dict[str, Any] = {"start": start, "count": count}
        if queue:
            params["queue"] = queue
        return self._request(url, params=params)

    def get_match(self, region: str, match_id: str) -> dict[str, Any]:
        if match_id in self._match_cache:
            return self._match_cache[match_id]
        if self.match_store:
            stored_match = self.match_store.get_match(match_id)
            if stored_match:
                self._match_cache[match_id] = stored_match
                return stored_match
        url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        match = self._request(url)
        self._match_cache[match_id] = match
        if self.match_store:
            self.match_store.save_match(region, match)
        return match


def match_end_timestamp(match: dict[str, Any]) -> int:
    return int(match.get("info", {}).get("gameEndTimestamp", 0))


def collect_match_ids(
    client: RiotApiClient,
    region: str,
    puuid: str,
    *,
    count: int,
    queue: int | None = None,
) -> list[str]:
    match_ids: list[str] = []
    seen_ids: set[str] = set()

    for start in range(0, count, MATCHLIST_PAGE_SIZE):
        page_size = min(MATCHLIST_PAGE_SIZE, count - start)
        page_ids = client.get_match_ids(region, puuid, count=page_size, queue=queue, start=start)
        for match_id in page_ids:
            if match_id in seen_ids:
                continue
            seen_ids.add(match_id)
            match_ids.append(match_id)

        if len(page_ids) < page_size:
            break

    return match_ids


def collect_mode_matches(
    client: RiotApiClient,
    region: str,
    puuid: str,
    *,
    queue_ids: list[int],
    match_count: int,
    history_scan_count: int | None = None,
) -> list[dict[str, Any]]:
    candidate_ids: set[str] = set()
    for queue_id in queue_ids:
        for match_id in collect_match_ids(client, region, puuid, count=match_count, queue=queue_id):
            candidate_ids.add(match_id)

    if candidate_ids:
        matches = [client.get_match(region, match_id) for match_id in candidate_ids]
    else:
        matches = []
        scanned_ids = collect_match_ids(
            client,
            region,
            puuid,
            count=history_scan_count or match_count,
        )
        for match_id in scanned_ids:
            match = client.get_match(region, match_id)
            if match.get("info", {}).get("queueId") in queue_ids:
                matches.append(match)
                if len(matches) >= match_count:
                    break

    matches.sort(key=match_end_timestamp, reverse=True)
    return matches[:match_count]


def find_participant(match: dict[str, Any], puuid: str) -> dict[str, Any] | None:
    participants = match.get("info", {}).get("participants", [])
    for participant in participants:
        if participant.get("puuid") == puuid:
            return participant
    return None


def calculate_kill_participation(participant: dict[str, Any], participants: list[dict[str, Any]]) -> float:
    team_id = participant.get("teamId")
    team_kills = sum(p.get("kills", 0) for p in participants if p.get("teamId") == team_id)
    contributions = participant.get("kills", 0) + participant.get("assists", 0)
    return round_stat(safe_div(contributions, team_kills) * 100)


def profile_icon_url(version: str, icon_id: int) -> str:
    return f"https://ddragon.leagueoflegends.com/cdn/{version}/img/profileicon/{icon_id}.png"


def fetch_augment_catalog() -> dict[int, dict[str, Any]]:
    try:
        response = requests.get(COMMUNITY_DRAGON_ARENA_URL, timeout=30)
        response.raise_for_status()
        augments = response.json().get("augments", [])
    except (requests.RequestException, ValueError, AttributeError):
        return {}

    catalog = {}
    for augment in augments:
        augment_id = augment.get("id")
        if not isinstance(augment_id, int):
            continue
        icon_path = augment.get("iconSmall")
        catalog[augment_id] = {
            "id": augment_id,
            "name": augment.get("name") or f"Augment {augment_id}",
            "rarity": augment.get("rarity"),
            "iconUrl": f"{COMMUNITY_DRAGON_ASSET_BASE}/{icon_path}" if icon_path else None,
        }
    return catalog


def fetch_champion_catalog(version: str) -> dict[str, list[str]]:
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        champions = response.json().get("data", {})
    except (requests.RequestException, ValueError, AttributeError):
        return {}

    return {
        champion.get("name", champion_id): champion.get("tags", [])
        for champion_id, champion in champions.items()
    }


def champion_role(champion: str, champion_catalog: dict[str, list[str]]) -> str:
    if champion in ENCHANTER_CHAMPIONS:
        return "Enchanter"
    tags = champion_catalog.get(champion, [])
    return tags[0] if tags else "Unknown"


def participant_augments(
    participant: dict[str, Any],
    augment_catalog: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    augment_values = [
        (int(match.group(1)), value)
        for key, value in participant.items()
        if (match := re.fullmatch(r"playerAugment(\d+)", key)) and isinstance(value, int) and value > 0
    ]
    augment_values.sort()

    result = []
    seen_ids: set[int] = set()
    for _, augment_id in augment_values:
        if augment_id in seen_ids:
            continue
        seen_ids.add(augment_id)
        result.append(
            augment_catalog.get(
                augment_id,
                {
                    "id": augment_id,
                    "name": f"Augment {augment_id}",
                    "rarity": None,
                    "iconUrl": None,
                },
            )
        )
    return result


def is_top_augment_candidate(augment: dict[str, Any]) -> bool:
    name = " ".join(str(augment.get("name", "")).casefold().split())
    return name not in EXCLUDED_TOP_AUGMENT_NAMES


def champion_winrate(champion_stats: Counter[str], champion_wins: Counter[str]) -> list[dict[str, Any]]:
    items = []
    for champion, games in champion_stats.most_common(5):
        wins = champion_wins[champion]
        items.append(
            {
                "name": champion,
                "games": games,
                "wins": wins,
                "winRate": round_stat(safe_div(wins, games) * 100),
            }
        )
    return items


def augment_winrate(
    augment_stats: Counter[int],
    augment_wins: Counter[int],
    augment_details: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    items = []
    for augment_id, games in augment_stats.most_common(6):
        wins = augment_wins[augment_id]
        items.append(
            {
                **augment_details[augment_id],
                "games": games,
                "wins": wins,
                "winRate": round_stat(safe_div(wins, games) * 100),
            }
        )
    return items


def build_player_summary(
    player: dict[str, Any],
    matches: list[dict[str, Any]],
    augment_catalog: dict[int, dict[str, Any]],
    champion_catalog: dict[str, list[str]],
) -> dict[str, Any]:
    totals = defaultdict(float)
    champion_counts: Counter[str] = Counter()
    champion_wins: Counter[str] = Counter()
    augment_counts: Counter[int] = Counter()
    augment_wins: Counter[int] = Counter()
    augment_details: dict[int, dict[str, Any]] = {}
    role_counts: Counter[str] = Counter()
    recent_matches: list[dict[str, Any]] = []
    wins = 0

    for match in matches:
        participant = find_participant(match, player["puuid"])
        if not participant:
            continue

        participants = match["info"]["participants"]
        total_cs = participant.get("totalMinionsKilled", 0) + participant.get("neutralMinionsKilled", 0)
        won = bool(participant.get("win"))
        wins += int(won)
        champion = participant.get("championName", "Unknown")
        champion_counts[champion] += 1
        if won:
            champion_wins[champion] += 1
        role = champion_role(champion, champion_catalog)
        role_counts[role] += 1

        augments = participant_augments(participant, augment_catalog)
        for augment in augments:
            if not is_top_augment_candidate(augment):
                continue
            augment_id = augment["id"]
            augment_counts[augment_id] += 1
            augment_details[augment_id] = augment
            if won:
                augment_wins[augment_id] += 1

        totals["kills"] += participant.get("kills", 0)
        totals["deaths"] += participant.get("deaths", 0)
        totals["assists"] += participant.get("assists", 0)
        totals["cs"] += total_cs
        totals["gold"] += participant.get("goldEarned", 0)
        totals["damage"] += participant.get("totalDamageDealtToChampions", 0)
        totals["cc"] += participant.get("timeCCingOthers", 0)
        totals["healing"] += participant.get("totalHealsOnTeammates", 0)
        totals["shielding"] += participant.get("totalDamageShieldedOnTeammates", 0)
        totals["kp"] += calculate_kill_participation(participant, participants)

        recent_matches.append(
            {
                "matchId": match["metadata"]["matchId"],
                "champion": champion,
                "queueId": match["info"].get("queueId"),
                "result": "Win" if won else "Loss",
                "kills": participant.get("kills", 0),
                "deaths": participant.get("deaths", 0),
                "assists": participant.get("assists", 0),
                "kda": round_stat(
                    (participant.get("kills", 0) + participant.get("assists", 0))
                    / max(participant.get("deaths", 0), 1)
                ),
                "cs": total_cs,
                "gold": participant.get("goldEarned", 0),
                "damage": participant.get("totalDamageDealtToChampions", 0),
                "killParticipation": calculate_kill_participation(participant, participants),
                "augments": augments,
                "role": role,
                "playedAt": datetime.fromtimestamp(
                    match["info"].get("gameEndTimestamp", 0) / 1000, tz=timezone.utc
                ).isoformat(),
                "durationSeconds": match["info"].get("gameDuration", 0),
            }
        )

    games = len(recent_matches)
    avg_deaths = safe_div(totals["deaths"], games)
    summary = {
        "matches": games,
        "wins": wins,
        "winRate": round_stat(safe_div(wins, games) * 100),
        "avgKills": round_stat(safe_div(totals["kills"], games)),
        "avgDeaths": round_stat(avg_deaths),
        "avgAssists": round_stat(safe_div(totals["assists"], games)),
        "avgKda": round_stat(safe_div(totals["kills"] + totals["assists"], max(totals["deaths"], 1))),
        "avgCs": round_stat(safe_div(totals["cs"], games)),
        "avgGold": round_stat(safe_div(totals["gold"], games)),
        "avgDamage": round_stat(safe_div(totals["damage"], games)),
        "avgCcSeconds": round_stat(safe_div(totals["cc"], games)),
        "avgHealing": round_stat(safe_div(totals["healing"], games)),
        "avgShielding": round_stat(safe_div(totals["shielding"], games)),
        "avgKillParticipation": round_stat(safe_div(totals["kp"], games)),
    }

    return {
        "summary": summary,
        "top_champions": champion_winrate(champion_counts, champion_wins),
        "top_augments": augment_winrate(augment_counts, augment_wins, augment_details),
        "role_distribution": [
            {
                "role": role,
                "games": count,
                "share": round_stat(safe_div(count, sum(role_counts.values())) * 100),
            }
            for role, count in role_counts.most_common()
        ],
        "recent_matches": sorted(recent_matches, key=lambda item: item["playedAt"], reverse=True)[:8],
    }


def build_group_summary(players: list[dict[str, Any]], matches_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tracked_puuids = {player["puuid"]: player["display_name"] for player in players}
    shared_matches = 0
    wins = 0
    pair_stats: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"matches": 0, "wins": 0})
    champion_counts: Counter[str] = Counter()
    champion_wins: Counter[str] = Counter()

    for match in matches_by_id.values():
        participants = match.get("info", {}).get("participants", [])
        teams: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for participant in participants:
            if participant.get("puuid") in tracked_puuids:
                teams[participant.get("teamId", -1)].append(participant)

        for tracked_team in teams.values():
            if len(tracked_team) < 2:
                continue

            shared_matches += 1
            team_won = bool(tracked_team[0].get("win"))
            wins += int(team_won)
            names = sorted(tracked_puuids[p["puuid"]] for p in tracked_team)

            for idx, left in enumerate(names):
                for right in names[idx + 1 :]:
                    pair_key = (left, right)
                    pair_stats[pair_key]["matches"] += 1
                    pair_stats[pair_key]["wins"] += int(team_won)

            for participant in tracked_team:
                champion = participant.get("championName", "Unknown")
                champion_counts[champion] += 1
                if team_won:
                    champion_wins[champion] += 1

    pairs = [
        {
            "players": list(pair),
            "sharedMatches": values["matches"],
            "wins": values["wins"],
            "winRate": round_stat(safe_div(values["wins"], values["matches"]) * 100),
        }
        for pair, values in sorted(pair_stats.items(), key=lambda item: item[1]["matches"], reverse=True)
    ]

    return {
        "trackedPlayers": len(players),
        "sharedMatches": shared_matches,
        "wins": wins,
        "winRate": round_stat(safe_div(wins, shared_matches) * 100),
        "pairings": pairs[:6],
        "champions": champion_winrate(champion_counts, champion_wins),
    }


def fetch_live_data(
    config: dict[str, Any],
    api_key: str,
    match_store: TursoMatchStore | None = None,
) -> dict[str, Any]:
    client = RiotApiClient(api_key, match_store=match_store)
    ddragon_version = client.get_latest_ddragon_version()
    augment_catalog = fetch_augment_catalog()
    champion_catalog = fetch_champion_catalog(ddragon_version)
    resolved_players: list[dict[str, Any]] = []
    mode_matches_by_id: dict[str, dict[str, Any]] = {mode: {} for mode in MODE_QUEUES}

    for index, player in enumerate(config["players"], start=1):
        platform = player["platform"]
        region = PLATFORM_TO_REGION[platform]
        account = client.get_account_by_riot_id(region, player["game_name"], player["tag_line"])
        summoner = client.get_summoner_by_puuid(platform, account["puuid"])
        mode_matches: dict[str, list[dict[str, Any]]] = {}

        for mode, queue_ids in MODE_QUEUES.items():
            matches = collect_mode_matches(
                client,
                region,
                account["puuid"],
                queue_ids=queue_ids,
                match_count=config["match_count"],
                history_scan_count=config["history_scan_count"],
            )
            mode_matches[mode] = matches
            for match in matches:
                mode_matches_by_id[mode][match["metadata"]["matchId"]] = match

        resolved_players.append(
            {
                "id": f"player-{index}",
                "display_name": player["display_name"],
                "game_name": player["game_name"],
                "tag_line": player["tag_line"],
                "platform": platform,
                "puuid": account["puuid"],
                "summoner_level": summoner.get("summonerLevel", 0),
                "profile_icon_id": summoner.get("profileIconId", 0),
                "profile_icon_url": profile_icon_url(ddragon_version, summoner.get("profileIconId", 0)),
                "mode_matches": mode_matches,
            }
        )

    player_outputs = []
    for player in resolved_players:
        player_outputs.append(
            {
                "id": player["id"],
                "display_name": player["display_name"],
                "riot_id": f'{player["game_name"]}#{player["tag_line"]}',
                "puuid": player["puuid"],
                "region": player["platform"],
                "summoner_level": player["summoner_level"],
                "profile_icon_id": player["profile_icon_id"],
                "profile_icon_url": player["profile_icon_url"],
                "modes": {
                    mode: build_player_summary(player, matches, augment_catalog, champion_catalog)
                    for mode, matches in player["mode_matches"].items()
                },
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": config["title"],
        "defaultMode": "arena",
        "filters": {
            "matchCount": config["match_count"],
            "modes": [
                {
                    "id": mode,
                    "label": MODE_LABELS[mode],
                    "queues": MODE_QUEUES[mode],
                }
                for mode in MODE_QUEUES
            ],
        },
        "players": player_outputs,
        "group": {
            "modes": {
                mode: build_group_summary(resolved_players, matches)
                for mode, matches in mode_matches_by_id.items()
            }
        },
    }


def write_output(data: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate League of Legends dashboard data from Riot API.")
    parser.add_argument("--config", default="config/players.json", help="Path to the players config file.")
    parser.add_argument("--output", default="docs/data/stats.json", help="Path for generated JSON.")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    api_key = os.getenv("RIOT_API_KEY")
    if not api_key:
        raise SystemExit("Missing RIOT_API_KEY. Add it to your environment or .env file.")

    database_url = os.getenv("TURSO_DATABASE_URL")
    auth_token = os.getenv("TURSO_AUTH_TOKEN")
    if bool(database_url) != bool(auth_token):
        raise SystemExit("Set both TURSO_DATABASE_URL and TURSO_AUTH_TOKEN, or neither.")

    match_store = TursoMatchStore(database_url, auth_token) if database_url and auth_token else None
    try:
        config = load_config(Path(args.config))
        data = fetch_live_data(config, api_key, match_store)
        write_output(data, Path(args.output))
        print(f"Generated stats for {len(data['players'])} players -> {args.output}")
        if match_store:
            print(
                f"Turso match cache: {match_store.cache_hits} hits, "
                f"{match_store.cache_writes} new matches."
            )
    finally:
        if match_store:
            match_store.close()
