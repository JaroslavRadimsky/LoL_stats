const dataUrl = "./data/stats.json";

const state = {
  data: null,
  activeMode: null,
};

function formatPercent(value) {
  return `${Number(value ?? 0).toFixed(1)} %`;
}

function formatNumber(value) {
  return new Intl.NumberFormat("cs-CZ").format(value ?? 0);
}

function formatDate(isoString) {
  if (!isoString) {
    return "nezname";
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
    <small class="champ-meta">${pair.sharedMatches} spolecnych her</small>
  `;
  return card;
}

function createEmptyMessage(text) {
  const empty = document.createElement("p");
  empty.className = "champ-meta";
  empty.textContent = text;
  return empty;
}

function getModeDefinition(data, modeId) {
  return data.filters.modes.find((mode) => mode.id === modeId) ?? data.filters.modes[0];
}

function getModeLabel(data, modeId) {
  return getModeDefinition(data, modeId)?.label ?? modeId;
}

function getPlayerMode(player, modeId) {
  return (
    player.modes?.[modeId] ?? {
      summary: {
        matches: 0,
        wins: 0,
        winRate: 0,
        avgKills: 0,
        avgDeaths: 0,
        avgAssists: 0,
        avgKda: 0,
        avgCs: 0,
        avgGold: 0,
        avgDamage: 0,
        avgKillParticipation: 0,
      },
      top_champions: [],
      recent_matches: [],
    }
  );
}

function getGroupMode(data, modeId) {
  return (
    data.group?.modes?.[modeId] ?? {
      trackedPlayers: data.players.length,
      sharedMatches: 0,
      wins: 0,
      winRate: 0,
      pairings: [],
      champions: [],
    }
  );
}

function renderPlayer(player, modeId) {
  const modeData = getPlayerMode(player, modeId);
  const summary = modeData.summary;

  const template = document.getElementById("player-card-template");
  const fragment = template.content.cloneNode(true);
  const card = fragment.querySelector(".player-card");
  const avatar = fragment.querySelector(".avatar");
  const playerName = fragment.querySelector(".player-name");
  const playerId = fragment.querySelector(".player-id");
  const summaryGrid = fragment.querySelector(".summary-grid");
  const champList = fragment.querySelector(".champ-list");
  const recentList = fragment.querySelector(".recent-list");

  avatar.src = player.profile_icon_url;
  avatar.alt = `${player.display_name} icon`;
  playerName.textContent = player.display_name;
  playerId.textContent = `${player.riot_id} · lvl ${player.summoner_level}`;

  summaryGrid.append(
    createStatPill("Hry", formatNumber(summary.matches)),
    createStatPill("Winrate", formatPercent(summary.winRate)),
    createStatPill("KDA", Number(summary.avgKda ?? 0).toFixed(2)),
    createStatPill("Damage", formatNumber(Math.round(summary.avgDamage ?? 0))),
  );

  if (modeData.top_champions.length === 0) {
    champList.append(createEmptyMessage("Zatim bez nactenych her v tomhle modu."));
  } else {
    modeData.top_champions.forEach((champion) => champList.append(createChampionRow(champion)));
  }

  if (modeData.recent_matches.length === 0) {
    recentList.append(createEmptyMessage("Zadne zapasy pro vybrany mod."));
  } else {
    modeData.recent_matches.forEach((match) => recentList.append(createRecentRow(match)));
  }

  return card;
}

function renderModeSwitch() {
  const data = state.data;
  const modeSwitch = document.getElementById("mode-switch");
  modeSwitch.innerHTML = "";

  data.filters.modes.forEach((mode) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `mode-button${mode.id === state.activeMode ? " is-active" : ""}`;
    button.textContent = mode.label;
    button.addEventListener("click", () => {
      if (state.activeMode === mode.id) {
        return;
      }
      state.activeMode = mode.id;
      renderModeSwitch();
      renderDashboard();
    });
    modeSwitch.append(button);
  });
}

function renderDashboard() {
  const data = state.data;
  const modeLabel = getModeLabel(data, state.activeMode);
  const group = getGroupMode(data, state.activeMode);

  document.getElementById("page-title").textContent = data.title || "LoL Stats Dashboard";
  document.getElementById("page-subtitle").textContent =
    `Poslednich ${data.filters.matchCount} ${modeLabel} her na hrace. Prepinac okamzite meni pohled mezi ARAM a Arena statistikami.`;
  document.getElementById("generated-at").textContent = formatDate(data.generated_at);
  document.getElementById("shared-matches").textContent = formatNumber(group.sharedMatches);
  document.getElementById("filter-summary").textContent =
    `${data.players.length} hracu · ${modeLabel} · ${group.sharedMatches} spolecnych zapasu`;

  const groupMetrics = document.getElementById("group-metrics");
  groupMetrics.innerHTML = "";
  groupMetrics.append(
    createMetricCard("Pocet hracu", formatNumber(group.trackedPlayers), "sledovanych Riot ID"),
    createMetricCard("Squad winrate", formatPercent(group.winRate), `ve vybranem modu ${modeLabel}`),
    createMetricCard("Vyhry", formatNumber(group.wins), "sdilene hry"),
    createMetricCard(
      "Nejhranejsi pick",
      group.champions[0]?.name ?? "n/a",
      group.champions[0] ? `${group.champions[0].games} her` : "zatim bez dat",
    ),
  );

  const pairings = document.getElementById("pairings");
  pairings.innerHTML = "";
  if (group.pairings.length === 0) {
    pairings.append(createEmptyMessage("Zatim nejsou k dispozici spolecne dvojice."));
  } else {
    group.pairings.forEach((pair) => pairings.append(createPairCard(pair)));
  }

  const playerGrid = document.getElementById("player-grid");
  playerGrid.innerHTML = "";
  data.players.forEach((player) => playerGrid.append(renderPlayer(player, state.activeMode)));
}

async function loadData() {
  if (typeof window.fetch === "function") {
    const response = await window.fetch(dataUrl, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Nepodarilo se nacist ${dataUrl}`);
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
        reject(new Error(`Nepodarilo se nacist ${dataUrl}`));
      }
    };
    request.onerror = () => reject(new Error(`Nepodarilo se nacist ${dataUrl}`));
    request.send();
  });
}

async function main() {
  try {
    const data = await loadData();
    state.data = data;
    state.activeMode = data.defaultMode ?? data.filters.modes[0]?.id ?? "aram";
    renderModeSwitch();
    renderDashboard();
  } catch (error) {
    document.getElementById("filter-summary").textContent = "Nacitani selhalo.";
    const playerGrid = document.getElementById("player-grid");
    const message = document.createElement("article");
    message.className = "player-card";
    message.innerHTML = `
      <h3>Data nejsou k dispozici</h3>
      <p class="hero-text">Zkontroluj, ze existuje soubor <code>docs/data/stats.json</code> a obsahuje validni JSON.</p>
      <p class="champ-meta">${error.message}</p>
    `;
    playerGrid.append(message);
  }
}

main();
