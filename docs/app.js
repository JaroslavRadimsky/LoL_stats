const dataUrl = "./data/stats.json";

function formatPercent(value) {
  return `${Number(value ?? 0).toFixed(1)} %`;
}

function formatNumber(value) {
  return new Intl.NumberFormat("cs-CZ").format(value ?? 0);
}

function formatDate(isoString) {
  if (!isoString) {
    return "neznámé";
  }
  return new Intl.DateTimeFormat("cs-CZ", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(isoString));
}

function createMetricCard(label, value, hint = "") {
  const wrapper = document.createElement("div");
  wrapper.className = "metric-card";
  wrapper.innerHTML = `
    <span class="meta-label">${label}</span>
    <strong>${value}</strong>
    <small class="champ-meta">${hint}</small>
  `;
  return wrapper;
}

function createStatPill(label, value) {
  const item = document.createElement("div");
  item.className = "stat-pill";
  item.innerHTML = `
    <span class="meta-label">${label}</span>
    <strong>${value}</strong>
  `;
  return item;
}

function createRankCard(label, ranked) {
  const card = document.createElement("div");
  card.className = "rank-card";
  card.innerHTML = `
    <span class="meta-label">${label}</span>
    <strong>${ranked ? `${ranked.tier} ${ranked.rank}` : "Unranked"}</strong>
    <small class="champ-meta">${ranked ? `${ranked.leaguePoints} LP · ${formatPercent(ranked.winRate)}` : "Bez ranked dat"}</small>
  `;
  return card;
}

function createChampionRow(champion) {
  const row = document.createElement("div");
  row.className = "champ-row";
  row.innerHTML = `
    <div class="row-top">
      <strong>${champion.name}</strong>
      <span class="champ-meta">${champion.games} her · ${formatPercent(champion.winRate)}</span>
    </div>
    <div class="bar"><span style="width:${Math.max(champion.winRate, 4)}%"></span></div>
  `;
  return row;
}

function createRecentRow(match) {
  const row = document.createElement("div");
  row.className = "recent-row";
  const resultClass = match.result === "Win" ? "win" : "loss";
  row.innerHTML = `
    <div class="row-top">
      <strong>${match.champion}</strong>
      <span class="recent-result ${resultClass}">${match.result}</span>
    </div>
    <div class="recent-meta">
      ${match.kills}/${match.deaths}/${match.assists} · KDA ${match.kda} · ${match.cs} CS
    </div>
    <div class="recent-meta">
      ${formatDate(match.playedAt)}
    </div>
  `;
  return row;
}

function createPairCard(pair) {
  const card = document.createElement("div");
  card.className = "pair-card";
  card.innerHTML = `
    <span class="meta-label">${pair.players.join(" + ")}</span>
    <strong>${formatPercent(pair.winRate)}</strong>
    <small class="champ-meta">${pair.sharedMatches} společných her</small>
  `;
  return card;
}

function renderPlayer(player) {
  const template = document.getElementById("player-card-template");
  const fragment = template.content.cloneNode(true);
  const card = fragment.querySelector(".player-card");
  const avatar = fragment.querySelector(".avatar");
  const playerName = fragment.querySelector(".player-name");
  const playerId = fragment.querySelector(".player-id");
  const rankRow = fragment.querySelector(".rank-row");
  const summaryGrid = fragment.querySelector(".summary-grid");
  const champList = fragment.querySelector(".champ-list");
  const recentList = fragment.querySelector(".recent-list");

  avatar.src = player.profile_icon_url;
  avatar.alt = `${player.display_name} icon`;
  playerName.textContent = player.display_name;
  playerId.textContent = `${player.riot_id} · lvl ${player.summoner_level}`;

  rankRow.append(
    createRankCard("SoloQ", player.ranked.soloq),
    createRankCard("Flex", player.ranked.flex),
  );

  const summary = player.summary;
  summaryGrid.append(
    createStatPill("Winrate", formatPercent(summary.winRate)),
    createStatPill("KDA", summary.avgKda.toFixed(2)),
    createStatPill("Průměrný CS", summary.avgCs.toFixed(1)),
    createStatPill("Damage", formatNumber(Math.round(summary.avgDamage))),
  );

  if (player.top_champions.length === 0) {
    const empty = document.createElement("p");
    empty.className = "champ-meta";
    empty.textContent = "Zatím bez načtených her.";
    champList.append(empty);
  } else {
    player.top_champions.forEach((champion) => champList.append(createChampionRow(champion)));
  }

  if (player.recent_matches.length === 0) {
    const empty = document.createElement("p");
    empty.className = "champ-meta";
    empty.textContent = "Žádné zápasy pro vybraný filtr.";
    recentList.append(empty);
  } else {
    player.recent_matches.forEach((match) => recentList.append(createRecentRow(match)));
  }

  return card;
}

async function loadData() {
  if (typeof window.fetch === "function") {
    const response = await window.fetch(dataUrl, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Nepodařilo se načíst ${dataUrl}`);
    }
    return response.json();
  }

  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("GET", dataUrl, true);
    request.responseType = "json";
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        resolve(request.response);
      } else {
        reject(new Error(`Nepodařilo se načíst ${dataUrl}`));
      }
    };
    request.onerror = () => reject(new Error(`Nepodařilo se načíst ${dataUrl}`));
    request.send();
  });
}

async function main() {
  try {
    const data = await loadData();
    document.getElementById("page-title").textContent = data.title || "LoL Stats Dashboard";
    document.getElementById("page-subtitle").textContent =
      `Posledních ${data.filters.matchCount} her na hráče${data.filters.queue ? ` · queue ${data.filters.queue}` : ""}.`;
    document.getElementById("generated-at").textContent = formatDate(data.generated_at);
    document.getElementById("shared-matches").textContent = formatNumber(data.group.sharedMatches);
    document.getElementById("filter-summary").textContent =
      `${data.players.length} hráčů · ${data.group.sharedMatches} společných zápasů`;

    const groupMetrics = document.getElementById("group-metrics");
    groupMetrics.append(
      createMetricCard("Počet hráčů", formatNumber(data.group.trackedPlayers), "sledovaných Riot ID"),
      createMetricCard("Squad winrate", formatPercent(data.group.winRate), "ve společných zápasech"),
      createMetricCard("Výhry", formatNumber(data.group.wins), "sdílené hry"),
      createMetricCard(
        "Nejhranější pick",
        data.group.champions[0]?.name ?? "n/a",
        data.group.champions[0] ? `${data.group.champions[0].games} her` : "zatím bez dat",
      ),
    );

    const pairings = document.getElementById("pairings");
    if (data.group.pairings.length === 0) {
      const empty = document.createElement("p");
      empty.className = "champ-meta";
      empty.textContent = "Zatím nejsou k dispozici společné dvojice.";
      pairings.append(empty);
    } else {
      data.group.pairings.forEach((pair) => pairings.append(createPairCard(pair)));
    }

    const playerGrid = document.getElementById("player-grid");
    data.players.forEach((player) => playerGrid.append(renderPlayer(player)));
  } catch (error) {
    document.getElementById("filter-summary").textContent = "Načtení selhalo.";
    const playerGrid = document.getElementById("player-grid");
    const message = document.createElement("article");
    message.className = "player-card";
    message.innerHTML = `
      <h3>Data nejsou k dispozici</h3>
      <p class="hero-text">Zkontroluj, že existuje soubor <code>docs/data/stats.json</code> a obsahuje validní JSON.</p>
      <p class="champ-meta">${error.message}</p>
    `;
    playerGrid.append(message);
  }
}

main();
