# LoL Stats Dashboard

Python projekt, který stáhne statistiky z Riot API a vykreslí je do statického webu vhodného pro GitHub Pages.

## Jak to funguje

- Python skript načte Riot ID tebe a tvých kamarádů z `config/players.json`.
- Zavolá Riot API a spočítá souhrny z posledních zápasů.
- Pokud jsou nastavené Turso údaje, uloží nové zápasy do databáze a již známé zápasy znovu nestahuje.
- Výsledek uloží do `docs/data/stats.json`.
- Statický frontend v `docs/` si JSON načte a vykreslí dashboard.
- GitHub Pages pak hostuje jen HTML, CSS, JS a vygenerovaný JSON.

To je důležité, protože GitHub Pages neumí hostovat Python backend. Oficiální dokumentace GitHubu popisuje Pages jako statický hosting a doporučuje GitHub Actions pro vlastní build/deploy workflow: [What is GitHub Pages?](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [Configuring a publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site). Riot zároveň doporučuje pracovat s Riot ID a PUUID místo starých summoner name endpointů: [Riot LoL docs](https://developer.riotgames.com/docs/lol), [Riot APIs reference](https://developer.riotgames.com/apis).

## Lokální spuštění

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

Vytvoř `.env` s klíčem:

```env
RIOT_API_KEY=RGAPI-...
```

Doplň hráče do `config/players.json` podle vzoru v `config/players.example.json`.

Pak vygeneruj data:

```powershell
python -m lol_stats --config config/players.json --output docs/data/stats.json
```

Pro rychlý náhled webu můžeš použít třeba:

```powershell
python -m http.server 8000 -d docs
```

## Turso databáze

Turso je volitelné při lokálním spuštění, ale doporučené pro pravidelné GitHub Actions buildy. Databáze uchovává celý původní Riot match JSON a zároveň normalizované tabulky:

- `matches`
- `participants`
- `participant_augments`

Po instalaci [Turso CLI](https://docs.turso.tech/cli/installation) vytvoř databázi:

```bash
turso auth login
turso db create lol-stats
turso db show --url lol-stats
turso db tokens create lol-stats
```

Získané hodnoty nastav lokálně podle `.env.example`:

```env
TURSO_DATABASE_URL=libsql://...
TURSO_AUTH_TOKEN=...
```

Při prvním generování se zápasy stáhnou z Riot API a uloží do Turso. Při dalších generováních se jejich detaily načtou z databáze a z Riot API se stáhnou pouze nové zápasy.

## Riot config

Ukázkový config:

```json
{
  "title": "Naše Flex statistiky",
  "match_count": 20,
  "history_scan_count": 20,
  "players": [
    {
      "display_name": "Ja",
      "game_name": "MojeRiotJmeno",
      "tag_line": "EUW",
      "platform": "euw1"
    }
  ]
}
```

Podporované `platform` hodnoty v tomto projektu:

- `euw1`
- `eun1`
- `na1`
- `kr`
- `br1`
- `la1`
- `la2`
- `oc1`
- `ru`
- `tr1`
- `jp1`
- `ph2`
- `sg2`
- `th2`
- `tw2`
- `vn2`

`history_scan_count` je volitelné. Použije se jako záloha pro nové nebo experimentální fronty, kdy Riot matchlist endpoint nevrátí nic pro konkrétní `queue`, ale zápasy jsou dostupné v nefiltrované historii. Bez nastavení se skenuje posledních 20 her; pokud ARAM: Mayhem nevidíš a víš, že je mezi staršími hrami, zvyš třeba na `100` nebo `200`.

## GitHub nasazení

Repo už obsahuje workflow v `.github/workflows/deploy-pages.yml`.

Na GitHubu stačí:

1. Přidat secret `RIOT_API_KEY`.
2. Přidat secrets `TURSO_DATABASE_URL` a `TURSO_AUTH_TOKEN`.
3. Nastavit GitHub Pages source na `GitHub Actions`.
4. Přidat vlastní `config/players.json`.
5. Pushnout repozitář.

Workflow při deployi:

- nainstaluje Python závislosti,
- pokud najde `config/players.json` a secret, vygeneruje reálná data,
- jinak ponechá demo data,
- nasadí obsah `docs/` na GitHub Pages.

## Co dashboard ukazuje

- rank a winrate pro SoloQ/Flex
- souhrn z posledních zápasů
- top championy
- poslední odehrané hry
- společné zápasy mezi sledovanými hráči
- jednoduchý přehled dvojic s nejlepší synergií
