const dataUrl = "./data/stats.json";

const state = {
  data: null,
  activeMode: null,
};

const excludedTopAugmentNames = new Set([
  "compulsion for power",
  "gain a prismatic stat anvil",
  "level augments",
  "replace augment",
]);

function isTopAugmentCandidate(augment) {
  const normalizedName = String(augment.name ?? "")
    .toLocaleLowerCase("en-US")
    .trim()
    .replace(/\s+/g, " ");
  return !excludedTopAugmentNames.has(normalizedName);
}

function formatPercent(value) {
  return `${Number(value ?? 0).toFixed(1)}\u00a0%`;
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

function createChampionRow(champion) {
  const row = document.createElement("div");
  row.className = "champ-row";
  row.innerHTML = `
    <div class="row-top">
      <strong>${champion.name}</strong>
      <span class="champ-meta">${champion.games} her &middot; ${formatPercent(champion.winRate)}</span>
    </div>
    <div class="bar"><span style="width:${Math.max(champion.winRate, 4)}%"></span></div>
  `;
  return row;
}

function createRecentRow(match, modeId) {
  const row = document.createElement("div");
  row.className = "recent-row";
  const resultClass = match.result === "Win" ? "win" : "loss";
  const augments = match.augments ?? [];
  const performance =
    modeId === "arena"
      ? `${formatNumber(match.damage)} damage`
      : `KDA ${match.kda} &middot; ${match.cs} CS`;
  row.innerHTML = `
    <div class="row-top">
      <strong>${match.champion}</strong>
      <span class="recent-result ${resultClass}">${match.result}</span>
    </div>
    <div class="recent-meta">
      ${match.kills}/${match.deaths}/${match.assists} &middot; ${performance}
    </div>
    <div class="recent-meta">${formatDate(match.playedAt)}</div>
    ${
      augments.length
        ? `<div class="augment-list" aria-label="Augmenty">${augments
            .map(
              (augment) => `
                <div class="augment" title="${augment.name}">
                  ${
                    augment.iconUrl
                      ? `<img src="${augment.iconUrl}" alt="" loading="lazy" />`
                      : `<span class="augment-fallback">${augment.id}</span>`
                  }
                  <span>${augment.name}</span>
                </div>
              `,
            )
            .join("")}</div>`
        : ""
    }
  `;
  return row;
}

function createTopAugment(augment) {
  const item = document.createElement("div");
  item.className = "top-augment";
  item.innerHTML = `
    ${
      augment.iconUrl
        ? `<img src="${augment.iconUrl}" alt="" loading="lazy" />`
        : `<span class="augment-fallback">${augment.id}</span>`
    }
    <div>
      <strong>${augment.name}</strong>
      <span class="champ-meta">${augment.games} výběrů &middot; ${formatPercent(augment.winRate)}</span>
    </div>
  `;
  return item;
}

function createRoleRow(role) {
  const row = document.createElement("div");
  row.className = "role-row";
  row.innerHTML = `
    <div class="row-top">
      <strong>${role.role}</strong>
      <span class="champ-meta">${role.games} her &middot; ${formatPercent(role.share)}</span>
    </div>
    <div class="bar role-bar"><span style="width:${Math.max(role.share, 3)}%"></span></div>
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

function createEmptyMessage(text) {
  const empty = document.createElement("p");
  empty.className = "champ-meta";
  empty.textContent = text;
  return empty;
}

function deriveTopAugments(matches) {
  const stats = new Map();
  matches.forEach((match) => {
    (match.augments ?? []).forEach((augment) => {
      if (!isTopAugmentCandidate(augment)) {
        return;
      }
      const current = stats.get(augment.id) ?? { ...augment, games: 0, wins: 0 };
      current.games += 1;
      current.wins += match.result === "Win" ? 1 : 0;
      stats.set(augment.id, current);
    });
  });
  return [...stats.values()]
    .sort((left, right) => right.games - left.games)
    .slice(0, 6)
    .map((augment) => ({ ...augment, winRate: (augment.wins / augment.games) * 100 }));
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
        avgKda: 0,
        avgDamage: 0,
        avgCcSeconds: 0,
        avgHealing: 0,
        avgShielding: 0,
        avgKillParticipation: 0,
      },
      top_champions: [],
      top_augments: [],
      role_distribution: [],
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
  const summaryGrid = fragment.querySelector(".summary-grid");
  const detailMetrics = fragment.querySelector(".detail-metrics");
  const champList = fragment.querySelector(".champ-list");
  const roleChart = fragment.querySelector(".role-chart");
  const topAugmentList = fragment.querySelector(".top-augment-list");
  const recentList = fragment.querySelector(".recent-list");
  const playerToggle = fragment.querySelector(".player-toggle");
  const playerDetail = fragment.querySelector(".player-detail");

  avatar.src = player.profile_icon_url;
  avatar.alt = `${player.display_name} icon`;
  fragment.querySelector(".player-name").textContent = player.display_name;
  fragment.querySelector(".player-id").textContent = `${player.riot_id} · lvl ${player.summoner_level}`;
  fragment.querySelector(".recent-count").textContent = modeData.recent_matches.length
    ? `${modeData.recent_matches.length} her`
    : "";

  const modeSpecificStat =
    modeId === "arena"
      ? createStatPill("Kill participation", formatPercent(summary.avgKillParticipation))
      : createStatPill("KDA", Number(summary.avgKda ?? 0).toFixed(2));
  summaryGrid.append(
    createStatPill("Hry", formatNumber(summary.matches)),
    createStatPill("Winrate", formatPercent(summary.winRate)),
    modeSpecificStat,
  );
  detailMetrics.append(
    createStatPill("Damage", formatNumber(Math.round(summary.avgDamage ?? 0))),
    createStatPill("CC", `${formatNumber(Math.round(summary.avgCcSeconds ?? 0))} s`),
    createStatPill("Healing allies", formatNumber(Math.round(summary.avgHealing ?? 0))),
    createStatPill("Shielding allies", formatNumber(Math.round(summary.avgShielding ?? 0))),
  );

  if (modeData.top_champions.length === 0) {
    champList.append(createEmptyMessage("Zatím bez načtených her v tomhle módu."));
  } else {
    modeData.top_champions.forEach((champion) => champList.append(createChampionRow(champion)));
  }

  if ((modeData.role_distribution ?? []).length === 0) {
    roleChart.append(createEmptyMessage("Role se doplní při příštím generování dat."));
  } else {
    modeData.role_distribution.forEach((role) => roleChart.append(createRoleRow(role)));
  }

  const topAugments =
    (modeData.top_augments ?? []).length > 0
      ? modeData.top_augments.filter(isTopAugmentCandidate)
      : deriveTopAugments(modeData.recent_matches);
  if (topAugments.length === 0) {
    topAugmentList.append(createEmptyMessage("V tomto módu nejsou dostupné augmenty."));
  } else {
    topAugments.forEach((augment) => topAugmentList.append(createTopAugment(augment)));
  }

  if (modeData.recent_matches.length === 0) {
    recentList.append(createEmptyMessage("Žádné zápasy pro vybraný mód."));
  } else {
    modeData.recent_matches.forEach((match) => recentList.append(createRecentRow(match, modeId)));
  }

  playerToggle.addEventListener("click", () => {
    const willOpen = playerDetail.hidden;
    playerDetail.hidden = !willOpen;
    playerToggle.setAttribute("aria-expanded", String(willOpen));
    playerToggle.querySelector("span:first-child").textContent = willOpen
      ? "Skrýt detail hráče"
      : "Zobrazit detail hráče";
    playerToggle.querySelector(".toggle-icon").textContent = willOpen ? "−" : "+";
    card.classList.toggle("is-expanded", willOpen);
  });

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
      if (state.activeMode !== mode.id) {
        state.activeMode = mode.id;
        renderModeSwitch();
        renderDashboard();
      }
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
    `Posledních ${data.filters.matchCount} ${modeLabel} her na hráče. Přepínač okamžitě mění pohled mezi ARAM a Arena statistikami.`;
  document.getElementById("generated-at").textContent = formatDate(data.generated_at);
  document.getElementById("shared-matches").textContent = formatNumber(group.sharedMatches);
  document.getElementById("filter-summary").textContent =
    `${data.players.length} hráčů · ${modeLabel} · ${group.sharedMatches} společných zápasů`;

  const groupMetrics = document.getElementById("group-metrics");
  groupMetrics.innerHTML = "";
  groupMetrics.append(
    createMetricCard("Počet hráčů", formatNumber(group.trackedPlayers), "sledovaných Riot ID"),
    createMetricCard("Squad winrate", formatPercent(group.winRate), `ve vybraném módu ${modeLabel}`),
    createMetricCard("Výhry", formatNumber(group.wins), "sdílené hry"),
    createMetricCard(
      "Nejhranější pick",
      group.champions[0]?.name ?? "n/a",
      group.champions[0] ? `${group.champions[0].games} her` : "zatím bez dat",
    ),
  );

  const pairings = document.getElementById("pairings");
  pairings.innerHTML = "";
  if (group.pairings.length === 0) {
    pairings.append(createEmptyMessage("Zatím nejsou k dispozici společné dvojice."));
  } else {
    group.pairings.forEach((pair) => pairings.append(createPairCard(pair)));
  }

  const playerGrid = document.getElementById("player-grid");
  playerGrid.innerHTML = "";
  data.players.forEach((player) => playerGrid.append(renderPlayer(player, state.activeMode)));
}

async function loadData() {
  const response = await window.fetch(dataUrl, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Nepodařilo se načíst ${dataUrl}`);
  }
  return response.json();
}

async function main() {
  try {
    const data = await loadData();
    state.data = data;
    state.activeMode = data.defaultMode ?? data.filters.modes[0]?.id ?? "aram";
    renderModeSwitch();
    renderDashboard();
  } catch (error) {
    document.getElementById("filter-summary").textContent = "Načítání selhalo.";
    const playerGrid = document.getElementById("player-grid");
    const message = document.createElement("article");
    message.className = "player-card";
    message.innerHTML = `
      <h3>Data nejsou k dispozici</h3>
      <p class="hero-text">Zkontroluj soubor <code>docs/data/stats.json</code>.</p>
      <p class="champ-meta">${error.message}</p>
    `;
    playerGrid.append(message);
  }
}

main();
