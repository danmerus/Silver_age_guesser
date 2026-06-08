import json
import math
import random
import sqlite3
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request

DB_PATH = Path(__file__).parent / "poems.db"
TURNS = 5
MAX_YEAR_DIFF = 10
YEAR_MIN = 1880
YEAR_MAX = 1940

_portraits_path = Path(__file__).parent / "static" / "portraits.json"
PORTRAITS: dict[str, list[str]] = (
    json.loads(_portraits_path.read_text("utf-8")) if _portraits_path.exists() else {}
)

app = Flask(__name__)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def pick_excerpt(text: str, max_lines: int = 6) -> str:
    stanzas = [s.strip() for s in text.split("\n\n") if len(s.strip().splitlines()) >= 2]
    if not stanzas:
        stanzas = [text.strip()]

    chosen = random.choice(stanzas)
    lines = chosen.splitlines()
    if len(lines) > max_lines:
        start = random.randint(0, len(lines) - max_lines)
        lines = lines[start : start + max_lines]
    return "\n".join(lines)


def score_guess(author_guess: str, year_guess: int, actual_author: str, actual_year: int | None) -> dict:
    author_score = 2500 if author_guess.strip() == actual_author else 0
    if actual_year is None:
        return {"author": author_score, "year": None, "total": author_score, "year_diff": None}
    diff = abs(year_guess - actual_year)
    year_score = max(0, round(2500 * (1 - diff / MAX_YEAR_DIFF)))
    return {
        "author": author_score,
        "year": year_score,
        "total": author_score + year_score,
        "year_diff": diff,
    }


# ── Routes ──────────────────────────────────────────────────────────────────

def get_author_names() -> list[str]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT author_name FROM poems ORDER BY author_name",
        ).fetchall()
    return [r["author_name"] for r in rows]


@app.route("/")
def index():
    return render_template("index.html", authors=get_author_names())


@app.route("/api/game/start", methods=["POST"])
def start_game():
    data = request.get_json()
    player_name = (data.get("name") or "Аноним").strip()[:50]

    with get_db() as conn:
        rows = conn.execute(
            "SELECT author_slug, COUNT(*) n FROM poems GROUP BY author_slug"
        ).fetchall()
        authors = [r["author_slug"] for r in rows]
        weights = [math.log(r["n"]) for r in rows]

        # Sample TURNS distinct authors without replacement, log-weighted
        chosen: list[str] = []
        remaining = list(zip(authors, weights))
        for _ in range(min(TURNS, len(remaining))):
            total = sum(w for _, w in remaining)
            pick = random.uniform(0, total)
            cum = 0.0
            for i, (slug, w) in enumerate(remaining):
                cum += w
                if pick <= cum:
                    chosen.append(slug)
                    remaining.pop(i)
                    break

        # Pick one random poem per chosen author
        poem_id_rows = []
        for slug in chosen:
            row = conn.execute(
                "SELECT id FROM poems WHERE author_slug=? ORDER BY RANDOM() LIMIT 1",
                (slug,),
            ).fetchone()
            if row:
                poem_id_rows.append(row)

    if len(poem_id_rows) < TURNS:
        return jsonify({"error": "Not enough poems in DB"}), 500

    poem_ids = [r["id"] for r in poem_id_rows]
    game_id = str(uuid.uuid4())

    with get_db() as conn:
        conn.execute(
            "INSERT INTO games (id, player_name, poem_ids) VALUES (?,?,?)",
            (game_id, player_name, json.dumps(poem_ids)),
        )

    first_poem = _get_poem_for_turn(poem_ids[0])
    return jsonify({
        "game_id": game_id,
        "turn": 0,
        "total_turns": TURNS,
        "poem": first_poem,
    })


@app.route("/api/game/guess", methods=["POST"])
def guess():
    data = request.get_json()
    game_id = data.get("game_id")
    author_guess = (data.get("author") or "").strip()
    try:
        year_guess = int(data.get("year", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid year"}), 400

    with get_db() as conn:
        game = conn.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
        if not game:
            return jsonify({"error": "Game not found"}), 404
        if game["finished"]:
            return jsonify({"error": "Game already finished"}), 400

        poem_ids = json.loads(game["poem_ids"])
        scores = json.loads(game["scores"])
        turn = game["current_turn"]

        poem_id = poem_ids[turn]
        poem = conn.execute("SELECT * FROM poems WHERE id=?", (poem_id,)).fetchone()

        result = score_guess(author_guess, year_guess, poem["author_name"], poem["year"])
        scores.append(result)
        next_turn = turn + 1
        finished = next_turn >= TURNS

        conn.execute(
            "UPDATE games SET current_turn=?, scores=?, finished=? WHERE id=?",
            (next_turn, json.dumps(scores), int(finished), game_id),
        )

        if finished:
            total = sum(s["total"] for s in scores)
            conn.execute(
                "INSERT INTO leaderboard (player_name, total_score) VALUES (?,?)",
                (game["player_name"], total),
            )

    slug = poem["author_slug"]
    portraits = PORTRAITS.get(slug, [])
    portrait = random.choice(portraits) if portraits else None

    response = {
        "turn": turn,
        "score": result,
        "correct": {
            "author": poem["author_name"],
            "year": poem["year"],
            "title": poem["title"],
            "portrait": portrait,
        },
        "full_poem": poem["text"],
        "finished": finished,
        "running_total": sum(s["total"] for s in scores),
    }

    if not finished:
        next_poem_id = poem_ids[next_turn]
        response["next_poem"] = _get_poem_for_turn(next_poem_id)
        response["next_turn"] = next_turn

    return jsonify(response)


@app.route("/api/leaderboard")
def leaderboard():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT player_name, total_score, finished_at FROM leaderboard ORDER BY total_score DESC LIMIT 20"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


def _get_poem_for_turn(poem_id: int) -> dict:
    with get_db() as conn:
        poem = conn.execute("SELECT * FROM poems WHERE id=?", (poem_id,)).fetchone()
    return {
        "id": poem["id"],
        "excerpt": pick_excerpt(poem["text"]),
        "has_year": poem["year"] is not None,
    }


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
