/* =========================================================
   EVG – script.js
   ========================================================= */

// ---------------------------------------------------------------------------
// Leaderboard auto-refresh (public page)
// ---------------------------------------------------------------------------

(function () {
  const tbody     = document.getElementById("leaderboard-tbody");
  const thead     = document.getElementById("leaderboard-thead");
  if (!tbody) return;

  const indicator = document.getElementById("refresh-indicator");
  const INTERVAL  = 30000; // 30 seconds

  // Read the current game-column IDs from the header (set by the server on initial render)
  function currentGameIds() {
    return Array.from(thead.querySelectorAll("th[data-game-id]"))
                .map(th => th.dataset.gameId);
  }

  function rankIcon(rank) {
    if (rank === 1) return '<span class="rank-1">🥇</span>';
    if (rank === 2) return '<span class="rank-2">🥈</span>';
    if (rank === 3) return '<span class="rank-3">🥉</span>';
    return `<span class="rank-other">${rank}</span>`;
  }

  function buildHeaders(games) {
    const fixed = `
      <tr>
        <th class="text-center" style="width:50px;">#</th>
        <th>Joueur</th>`;
    const gameCols = games.map(g => `
        <th class="text-center lb-game-col" data-game-id="${g.id}">
          ${escapeHtml(g.name)}
          <div class="lb-day-label">${g.day === 'samedi' ? 'Sam.' : 'Dim.'}</div>
        </th>`).join("");
    return fixed + gameCols + `
        <th class="text-center" style="min-width:90px;">Total</th>
      </tr>`;
  }

  function buildRow(entry, index, games) {
    const isLeader = index === 0 && entry.total_points > 0;
    const rowClass = isLeader ? "row-leader" : "";

    const gameCells = games.map(g => {
      const pts = entry.game_scores ? entry.game_scores[String(g.id)] : undefined;
      if (pts === null || pts === undefined) {
        return `<td class="text-center lb-game-cell"><span class="lb-dnp">—</span></td>`;
      }
      return `<td class="text-center lb-game-cell"><span class="lb-pts">${pts}</span></td>`;
    }).join("");

    return `
      <tr class="${rowClass}">
        <td class="text-center">${rankIcon(entry.rank)}</td>
        <td><a href="/joueur/${entry.id}" class="player-name-link">${escapeHtml(entry.name)}</a></td>
        ${gameCells}
        <td class="text-center"><span class="points-badge">${entry.total_points} pts</span></td>
      </tr>`;
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function refresh() {
    if (indicator) { indicator.textContent = "Actualisation…"; indicator.classList.add("refreshing"); }

    fetch("/api/leaderboard")
      .then(r => r.json())
      .then(data => {
        const { leaderboard, games } = data;

        // If the set of finished games changed, update headers too
        const freshIds  = games.map(g => String(g.id));
        const currentIds = currentGameIds();
        const headersChanged = JSON.stringify(freshIds) !== JSON.stringify(currentIds);
        if (headersChanged) {
          thead.innerHTML = buildHeaders(games);
        }

        tbody.innerHTML = leaderboard.map((e, i) => buildRow(e, i, games)).join("");

        if (indicator) {
          const now = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
          indicator.textContent = `Mis à jour à ${now}`;
          indicator.classList.remove("refreshing");
        }
      })
      .catch(() => {
        if (indicator) { indicator.textContent = "Erreur de connexion"; indicator.classList.remove("refreshing"); }
      });
  }

  setInterval(refresh, INTERVAL);
})();


// ---------------------------------------------------------------------------
// Team builder (admin – jeu_detail)
// ---------------------------------------------------------------------------

(function () {
  const container = document.getElementById("teams-container");
  if (!container) return;

  let teamIndex = container.querySelectorAll(".team-block").length;

  // Add team button
  const addBtn = document.getElementById("btn-add-team");
  if (addBtn) {
    addBtn.addEventListener("click", function () {
      teamIndex++;
      const allPlayers = JSON.parse(document.getElementById("all-players-json").textContent);
      const block = buildTeamBlock(teamIndex, `Équipe ${teamIndex}`, allPlayers, []);
      container.appendChild(block);
      updateRemoveButtons();
    });
  }

  // Remove team (delegated)
  container.addEventListener("click", function (e) {
    if (e.target.closest(".btn-remove-team")) {
      const block = e.target.closest(".team-block");
      if (container.querySelectorAll(".team-block").length > 1) {
        block.remove();
        updateRemoveButtons();
      }
    }
  });

  function updateRemoveButtons() {
    const blocks = container.querySelectorAll(".team-block");
    blocks.forEach(b => {
      const btn = b.querySelector(".btn-remove-team");
      if (btn) btn.style.display = blocks.length > 1 ? "" : "none";
    });
  }

  function buildTeamBlock(idx, name, allPlayers, selectedIds) {
    const div = document.createElement("div");
    div.className = "team-block";

    const checkboxes = allPlayers.map(p => `
      <div class="form-check">
        <input class="form-check-input" type="checkbox"
               name="team_players_${idx}[]" value="${p.id}" id="p_${idx}_${p.id}"
               ${selectedIds.includes(p.id) ? "checked" : ""}>
        <label class="form-check-label" for="p_${idx}_${p.id}">${escapeHtml(p.name)}</label>
      </div>`).join("");

    div.innerHTML = `
      <div class="team-title">
        <input type="text" class="form-control form-control-sm d-inline-block w-auto"
               name="team_name_${idx}" value="${escapeHtml(name)}" required
               style="background:#1a1a3a;color:#fff;border-color:#444;font-weight:700;">
      </div>
      <button type="button" class="btn btn-sm btn-outline-danger btn-remove-team">✕</button>
      <div class="player-checkbox-list">${checkboxes}</div>
    `;
    return div;
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  updateRemoveButtons();

  // Client-side validation: warn if a player is in multiple teams
  const form = document.getElementById("teams-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      const checked = form.querySelectorAll("input[type=checkbox]:checked");
      const seen = {};
      let duplicate = false;
      checked.forEach(cb => {
        if (seen[cb.value]) duplicate = true;
        seen[cb.value] = true;
      });
      if (duplicate) {
        e.preventDefault();
        alert("Un joueur est assigné à plusieurs équipes. Veuillez corriger avant de sauvegarder.");
      }
    });
  }
})();


// ---------------------------------------------------------------------------
// Score config – add row
// ---------------------------------------------------------------------------

(function () {
  document.querySelectorAll(".btn-add-config-row").forEach(btn => {
    btn.addEventListener("click", function () {
      const gameType = btn.dataset.type;
      const tbody = document.getElementById(`config-tbody-${gameType}`);
      const rows  = tbody.querySelectorAll("tr");
      const nextPlacement = rows.length + 1;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${nextPlacement}e</td>
        <td>
          <input type="hidden" name="placement[]" value="${nextPlacement}">
          <input type="number" name="points[]" value="0" min="0"
                 class="form-control form-control-sm config-pts-input">
        </td>
        <td>
          <button type="button" class="btn btn-sm btn-outline-danger btn-remove-config-row">✕</button>
        </td>`;
      tbody.appendChild(tr);
    });
  });

  document.addEventListener("click", function (e) {
    if (e.target.closest(".btn-remove-config-row")) {
      e.target.closest("tr").remove();
    }
  });
})();
