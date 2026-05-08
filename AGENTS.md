# Agents.md — Guide for AI Coding Agents

This file gives an AI agent the context needed to work on this codebase confidently without having to explore everything from scratch.

---

## What this project is

**EVG** is a Python/Flask web app built for a bachelor party weekend ("EVG" = *Enterrement de Vie de Garçon*). It has two independent features:

1. **Score tracker** — tracks points across mini-games (team-based, individual, karting). Public leaderboard, admin portal to manage players/games/scores.
2. **NBA guessing game** — a Poeltl-style game where an admin picks a mystery NBA player and participants submit guesses. Each guess gets color-coded column hints (team, conference, division, position, jersey number, height, age).

The app is in **French** (UI, variable names in templates, flash messages). Python code uses English identifiers.

---

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Web framework | Flask 3 | No blueprints — all routes in `app.py` |
| Forms / CSRF | Flask-WTF | CSRF token auto-injected into every POST form by `base_admin.html` JS |
| Database | SQLite via `database.py` | Raw `sqlite3`, no ORM |
| NBA data | `nba_api` | Static player list (no network); per-player details via `stats.nba.com` |
| Frontend | Vanilla JS + Bootstrap 5 | No build step, no bundler |
| CSS | Custom dark theme in `static/style.css` | Bootstrap overrides + custom components |
| Package manager | `uv` (`uv.lock` + `pyproject.toml`) | Also `requirements.txt` for Render compatibility |
| Deployment | Render (`render.yaml` + `Procfile`) | Gunicorn in production |

---

## Project layout

```
app.py            All Flask routes and auth helpers (no blueprints)
database.py       All SQLite queries; init_db() runs migrations on startup
nba_game.py       NBA game logic: team mapping, player fetch, compare, in-memory state
static/
  style.css       Single stylesheet — dark theme vars, Bootstrap overrides, NBA styles
  script.js       Leaderboard auto-refresh + team builder UX
templates/
  base.html             Public layout (navbar)
  index.html            Public leaderboard
  joueur_detail.html    Player score breakdown
  nba/
    jeu.html            NBA game board (autocomplete + AJAX guess table)
  admin/
    base_admin.html     Admin layout — injects CSRF token into all POST forms via JS
    connexion.html      Login page
    dashboard.html      Admin home
    joueurs.html        Player management
    comptes.html        Admin account management
    jeux.html           Game list
    jeu_detail.html     Game detail (teams + results)
    configuration.html  Points-per-placement config
    nba_setup.html      NBA game admin (set target player, reset)
```

---

## Key conventions

### Routes (`app.py`)
- Public routes: no decorator
- Admin routes: `@login_required` decorator (checks `session["admin_id"]`)
- The NBA guess submission endpoint (`/nba/devine`) is `@csrf.exempt` because it receives JSON, not a form
- All admin form routes follow the pattern: `GET` renders template, `POST` validates + redirects (PRG pattern)

### Database (`database.py`)
- All queries are parameterised (`?` placeholders) — never string-format SQL
- `init_db()` is idempotent: safe to call on every startup (uses `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`)
- Returns `sqlite3.Row` objects (dict-like access by column name)

### NBA game (`nba_game.py`)
- **In-memory state only** — `game_state` dict is lost on server restart; no DB involvement
- `get_active_players()` is cached after first call (static data, no network)
- `fetch_player_data(player_id)` makes one HTTP call to `stats.nba.com` (~1-2 s); wrap in try/except when calling from routes
- `TEAM_INFO` is a hardcoded dict of all 30 NBA teams (2024-25 season) mapping abbreviation → name/conference/division
- Comparison results use French keys: `"vert"` (green), `"jaune"` (yellow), `"rouge"` (red); direction values: `"haut"` (up), `"bas"` (down)

### CSS (`static/style.css`)
- CSS custom properties defined on `:root`: `--gold`, `--dark`, `--accent`, `--card-bg`
- NBA cell colors use `!important` on `background-color` and `color` to override Bootstrap's `.table` cell background
- NBA section starts at a clearly marked comment block at the bottom of the file

### Templates
- Public templates extend `base.html`
- Admin templates extend `admin/base_admin.html` which auto-injects CSRF tokens into all POST forms
- The NBA game board (`nba/jeu.html`) uses a Jinja2 macro `_render_cell` defined outside the `{% block %}` — this is valid in Jinja2 (macros at template root are accessible inside blocks)
- The guess table (`<table class="nba-guess-table w-100">`) deliberately does **not** use Bootstrap's `.table` class to avoid background-color override conflicts

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Flask session signing key |
| `INITIAL_ADMIN_USER` | Yes | Username of the first admin account |
| `INITIAL_ADMIN_PASSWORD` | Yes | Password (min 8 chars); account only created if no admin exists |
| `DATABASE_PATH` | No | Path to SQLite file (default: `evg.db`) |
| `FLASK_DEBUG` | No | Set to `1` for auto-reload in development |

The app **refuses to start** if `SECRET_KEY` or `INITIAL_ADMIN_PASSWORD` are missing.

---

## Running locally

```bash
uv sync
cp .env.example .env   # then fill in values
uv run python app.py
```

App is at `http://localhost:5000`. Admin at `/admin/connexion`.

---

## Common gotchas

- **NBA API latency**: `fetch_player_data()` calls `stats.nba.com` which can be slow or occasionally rate-limited. Always handle exceptions in routes and return a user-friendly flash/JSON error.
- **In-memory NBA state**: restarting the dev server clears the mystery player and all guesses. This is by design.
- **CSRF on admin forms**: `base_admin.html` injects the token via JS after DOM load. Any form added to an admin template gets it automatically — no need to add a hidden input manually.
- **SQLite on Render**: the DB file lives inside the ephemeral container and is wiped on every redeploy. Only use Render for short-lived events, not persistent data.
- **uv vs pip**: dependencies are managed with `uv`. Running `pip install -r requirements.txt` also works (the file is kept in sync for Render compatibility), but `uv sync` is preferred locally.
