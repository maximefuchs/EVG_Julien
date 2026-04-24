/* =========================================================
   EVG – script.js
   ========================================================= */

// ---------------------------------------------------------------------------
// Leaderboard auto-refresh (public page)
// ---------------------------------------------------------------------------

(function () {
  const table = document.getElementById("leaderboard-tbody");
  if (!table) return;

  const indicator = document.getElementById("refresh-indicator");
  const INTERVAL  = 30000; // 30 seconds

  function rankIcon(rank) {
    if (rank === 1) return '<span class="rank-1">🥇</span>';
    if (rank === 2) return '<span class="rank-2">🥈</span>';
    if (rank === 3) return '<span class="rank-3">🥉</span>';
    return `<span class="rank-other">${rank}</span>`;
  }

  function buildRow(entry, index) {
    const isLeader = index === 0 && entry.total_points > 0;
    const rowClass = isLeader ? "row-leader" : "";
    return `
      <tr class="${rowClass}">
        <td class="text-center">${rankIcon(entry.rank)}</td>
        <td>
          <a href="/joueur/${entry.id}" class="player-name-link">${escapeHtml(entry.name)}</a>
        </td>
        <td class="text-center">
          <span class="points-badge">${entry.total_points} pts</span>
        </td>
        <td class="text-center text-muted">${entry.games_played}</td>
      </tr>`;
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function refresh() {
    const jour = new URLSearchParams(window.location.search).get("jour") || "";
    const url  = "/api/leaderboard" + (jour ? `?jour=${jour}` : "");

    if (indicator) { indicator.textContent = "Actualisation…"; indicator.classList.add("refreshing"); }

    fetch(url)
      .then(r => r.json())
      .then(data => {
        table.innerHTML = data.map(buildRow).join("");
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
