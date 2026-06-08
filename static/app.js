"use strict";

const $ = id => document.getElementById(id);

let state = {
  gameId: null,
  playerName: "",
  turn: 0,
  runningTotal: 0,
  pendingNext: null,
  currentHasYear: true,
};

function showScreen(name) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  $(`screen-${name}`).classList.add("active");
}

// ── Year slider ──────────────────────────────────────────────────
$("year-slider").addEventListener("input", () => {
  $("year-display").textContent = $("year-slider").value;
});

// ── Start game ───────────────────────────────────────────────────
$("btn-start").addEventListener("click", async () => {
  const name = $("player-name").value.trim() || "Аноним";
  state.playerName = name;

  const res = await fetch("/api/game/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const data = await res.json();
  if (data.error) { alert(data.error); return; }

  state.gameId = data.game_id;
  state.turn = data.turn;
  state.runningTotal = 0;

  loadPoem(data.poem);
  showScreen("game");
});

// ── Submit guess ─────────────────────────────────────────────────
$("btn-guess").addEventListener("click", async () => {
  const author = $("author-input").value.trim();
  const year = parseInt($("year-slider").value);

  if (!author) { $("author-input").focus(); return; }

  $("btn-guess").disabled = true;

  const res = await fetch("/api/game/guess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_id: state.gameId, author, year }),
  });
  const data = await res.json();
  if (data.error) { alert(data.error); $("btn-guess").disabled = false; return; }

  state.runningTotal = data.running_total;
  state.pendingNext = data.finished ? null : { poem: data.next_poem, turn: data.next_turn };

  showResult(data);
});

// ── Next turn ────────────────────────────────────────────────────
$("btn-next").addEventListener("click", () => {
  if (state.pendingNext) {
    state.turn = state.pendingNext.turn;
    loadPoem(state.pendingNext.poem);
    showScreen("game");
  }
});

// ── Restart ──────────────────────────────────────────────────────
$("btn-restart").addEventListener("click", () => {
  state = { gameId: null, playerName: "", turn: 0, runningTotal: 0, pendingNext: null, currentHasYear: true };
  $("author-input").value = "";
  $("year-slider").value = 1905;
  $("year-display").textContent = 1905;
  showScreen("start");
  loadLeaderboard("leaderboard-preview");
});

// ── Helpers ──────────────────────────────────────────────────────
function loadPoem(poem) {
  $("excerpt").textContent = poem.excerpt;
  $("author-input").value = "";
  $("year-slider").value = 1905;
  $("year-display").textContent = 1905;
  $("btn-guess").disabled = false;
  $("turn-label").textContent = `Вопрос ${state.turn + 1} / 5`;
  $("running-score").textContent = `${state.runningTotal} очков`;

  // Show/hide year control depending on whether poem has a known year
  const yearGroup = $("year-slider").closest(".control-group");
  if (poem.has_year === false) {
    yearGroup.style.opacity = "0.35";
    yearGroup.style.pointerEvents = "none";
    $("year-display").textContent = "неизвестен";
  } else {
    yearGroup.style.opacity = "";
    yearGroup.style.pointerEvents = "";
  }
  state.currentHasYear = poem.has_year !== false;
}

function showResult(data) {
  const { score, correct, full_poem, finished, running_total } = data;

  // Author block
  const authorCorrect = score.author === 2500;
  $("res-author-score").textContent = score.author;
  $("res-author-detail").textContent = authorCorrect
    ? "✓ " + correct.author
    : correct.author;
  $("res-author-block").className = "score-block " + (authorCorrect ? "correct" : "wrong");

  // Year block — hidden/neutral when year is unknown
  if (score.year === null) {
    $("res-year-score").textContent = "—";
    $("res-year-detail").textContent = "год неизвестен";
    $("res-year-block").className = "score-block";
  } else {
    const yearExact = score.year_diff === 0;
    $("res-year-score").textContent = score.year;
    $("res-year-detail").textContent = yearExact
      ? `✓ ${correct.year}`
      : `${correct.year} (разница: ${score.year_diff} лет)`;
    $("res-year-block").className = "score-block " + (score.year > 0 ? "correct" : "wrong");
  }

  $("res-total-score").textContent = score.total;
  const yearLabel = correct.year ? `, ${correct.year}` : "";
  $("res-poem-title").textContent =
    `«${correct.title || "* * *"}» — ${correct.author}${yearLabel}`;

  $("full-poem").textContent = full_poem;
  $("running-score").textContent = `${running_total} очков`;

  if (finished) {
    $("btn-next").style.display = "none";
    // Will show end screen after user reads result
    $("btn-next").textContent = "Завершить";
    $("btn-next").style.display = "block";
    $("btn-next").onclick = () => showEnd(running_total);
  } else {
    $("btn-next").style.display = "block";
    $("btn-next").textContent = "Следующий вопрос →";
    $("btn-next").onclick = () => {
      if (state.pendingNext) {
        state.turn = state.pendingNext.turn;
        loadPoem(state.pendingNext.poem);
        showScreen("game");
      }
    };
  }

  showScreen("result");
}

async function showEnd(totalScore) {
  $("final-score").textContent = totalScore;
  await loadLeaderboard("leaderboard-final");
  showScreen("end");
}

async function loadLeaderboard(containerId) {
  const res = await fetch("/api/leaderboard");
  const rows = await res.json();
  const container = $(containerId);
  if (!rows.length) { container.innerHTML = ""; return; }

  const html = `
    <div class="leaderboard">
      <h3>Лучшие результаты</h3>
      ${rows.map((r, i) => `
        <div class="lb-row ${r.player_name === state.playerName ? "highlight" : ""}">
          <span class="lb-rank">${i + 1}.</span>
          <span class="lb-name">${escHtml(r.player_name)}</span>
          <span class="lb-score">${r.total_score}</span>
        </div>`).join("")}
    </div>`;
  container.innerHTML = html;
}

function escHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ── Init ─────────────────────────────────────────────────────────
loadLeaderboard("leaderboard-preview");
