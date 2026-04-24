import sqlite3
import os

DATABASE = os.environ.get("DATABASE_PATH", "evg.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS admins (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS games (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                day        TEXT NOT NULL CHECK(day IN ('samedi','dimanche')),
                type       TEXT NOT NULL CHECK(type IN ('mini_jeu','karting')),
                status     TEXT NOT NULL DEFAULT 'en_attente'
                               CHECK(status IN ('en_attente','en_cours','termine')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS game_teams (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id   INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
                name      TEXT NOT NULL,
                placement INTEGER
            );

            CREATE TABLE IF NOT EXISTS team_players (
                team_id   INTEGER NOT NULL REFERENCES game_teams(id) ON DELETE CASCADE,
                player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                PRIMARY KEY (team_id, player_id)
            );

            CREATE TABLE IF NOT EXISTS score_config (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                game_type  TEXT NOT NULL CHECK(game_type IN ('mini_jeu','karting')),
                placement  INTEGER NOT NULL,
                points     INTEGER NOT NULL DEFAULT 0,
                UNIQUE(game_type, placement)
            );
        """)

        # Default score config (only inserted if table is empty)
        existing = db.execute("SELECT COUNT(*) FROM score_config").fetchone()[0]
        if existing == 0:
            defaults = [
                ("mini_jeu", 1, 5), ("mini_jeu", 2, 4), ("mini_jeu", 3, 3),
                ("mini_jeu", 4, 2), ("mini_jeu", 5, 1), ("mini_jeu", 6, 0),
                ("karting",  1, 10), ("karting",  2, 8), ("karting",  3, 6),
                ("karting",  4, 4), ("karting",  5, 2), ("karting",  6, 1),
            ]
            db.executemany(
                "INSERT INTO score_config (game_type, placement, points) VALUES (?,?,?)",
                defaults
            )

        db.commit()


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

def get_leaderboard(day=None):
    """Return individual rankings, optionally filtered by day."""
    day_filter = "AND g.day = ?" if day else ""
    params = [day] if day else []

    with get_db() as db:
        rows = db.execute(f"""
            SELECT
                p.id,
                p.name,
                COALESCE(SUM(COALESCE(sc.points, 0)), 0) AS total_points,
                COUNT(DISTINCT CASE WHEN g.status = 'termine' THEN g.id END) AS games_played
            FROM players p
            LEFT JOIN team_players tp ON tp.player_id = p.id
            LEFT JOIN game_teams gt   ON gt.id = tp.team_id
                                     AND gt.placement IS NOT NULL
            LEFT JOIN games g         ON g.id = gt.game_id
                                     AND g.status = 'termine'
                                     {day_filter}
            LEFT JOIN score_config sc ON sc.game_type = g.type
                                     AND sc.placement = gt.placement
            GROUP BY p.id, p.name
            ORDER BY total_points DESC, p.name ASC
        """, params).fetchall()
    return [dict(r) for r in rows]


def get_player_game_breakdown(player_id):
    """Return point detail per game for a given player."""
    with get_db() as db:
        rows = db.execute("""
            SELECT
                g.name  AS game_name,
                g.day,
                g.type,
                gt.name AS team_name,
                gt.placement,
                COALESCE(sc.points, 0) AS points
            FROM team_players tp
            JOIN game_teams gt   ON gt.id = tp.team_id AND gt.placement IS NOT NULL
            JOIN games g         ON g.id = gt.game_id  AND g.status = 'termine'
            LEFT JOIN score_config sc ON sc.game_type = g.type
                                     AND sc.placement = gt.placement
            WHERE tp.player_id = ?
            ORDER BY g.created_at
        """, [player_id]).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

def get_all_players():
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM players ORDER BY name").fetchall()]


def add_player(name):
    with get_db() as db:
        db.execute("INSERT INTO players (name) VALUES (?)", [name.strip()])
        db.commit()


def rename_player(player_id, new_name):
    with get_db() as db:
        db.execute("UPDATE players SET name=? WHERE id=?", [new_name.strip(), player_id])
        db.commit()


def delete_player(player_id):
    with get_db() as db:
        db.execute("DELETE FROM players WHERE id=?", [player_id])
        db.commit()


# ---------------------------------------------------------------------------
# Admins
# ---------------------------------------------------------------------------

def get_all_admins():
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT id, username FROM admins ORDER BY username").fetchall()]


def get_admin_by_username(username):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM admins WHERE username=?", [username]).fetchone()
        return dict(row) if row else None


def add_admin(username, password_hash):
    with get_db() as db:
        db.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?,?)",
            [username.strip(), password_hash])
        db.commit()


def delete_admin(admin_id):
    with get_db() as db:
        db.execute("DELETE FROM admins WHERE id=?", [admin_id])
        db.commit()


def count_admins():
    with get_db() as db:
        return db.execute("SELECT COUNT(*) FROM admins").fetchone()[0]


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------

def get_all_games():
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM games ORDER BY day, created_at").fetchall()]


def get_game(game_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM games WHERE id=?", [game_id]).fetchone()
        return dict(row) if row else None


def create_game(name, day, game_type):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO games (name, day, type) VALUES (?,?,?)",
            [name.strip(), day, game_type])
        db.commit()
        return cur.lastrowid


def update_game_status(game_id, status):
    with get_db() as db:
        db.execute("UPDATE games SET status=? WHERE id=?", [status, game_id])
        db.commit()


def delete_game(game_id):
    with get_db() as db:
        db.execute("DELETE FROM games WHERE id=?", [game_id])
        db.commit()


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

def get_teams_for_game(game_id):
    """Return teams with their players for a game."""
    with get_db() as db:
        teams = [dict(r) for r in db.execute(
            "SELECT * FROM game_teams WHERE game_id=? ORDER BY id",
            [game_id]).fetchall()]
        for team in teams:
            team["players"] = [dict(r) for r in db.execute("""
                SELECT p.id, p.name FROM players p
                JOIN team_players tp ON tp.player_id = p.id
                WHERE tp.team_id = ?
                ORDER BY p.name
            """, [team["id"]]).fetchall()]
    return teams


def get_players_not_in_game(game_id):
    """Players not yet assigned to any team in this game."""
    with get_db() as db:
        return [dict(r) for r in db.execute("""
            SELECT p.id, p.name FROM players p
            WHERE p.id NOT IN (
                SELECT tp.player_id FROM team_players tp
                JOIN game_teams gt ON gt.id = tp.team_id
                WHERE gt.game_id = ?
            )
            ORDER BY p.name
        """, [game_id]).fetchall()]


def save_teams(game_id, teams_data):
    """
    teams_data: list of {"name": str, "player_ids": [int, ...]}
    Replaces all teams for the game.
    """
    with get_db() as db:
        db.execute("DELETE FROM game_teams WHERE game_id=?", [game_id])
        for team in teams_data:
            cur = db.execute(
                "INSERT INTO game_teams (game_id, name) VALUES (?,?)",
                [game_id, team["name"]])
            team_id = cur.lastrowid
            db.executemany(
                "INSERT INTO team_players (team_id, player_id) VALUES (?,?)",
                [(team_id, pid) for pid in team["player_ids"]])
        db.commit()


def save_results(game_id, placements):
    """
    placements: dict {team_id: placement_int}
    """
    with get_db() as db:
        for team_id, placement in placements.items():
            db.execute(
                "UPDATE game_teams SET placement=? WHERE id=? AND game_id=?",
                [placement, team_id, game_id])
        db.execute("UPDATE games SET status='termine' WHERE id=?", [game_id])
        db.commit()


# ---------------------------------------------------------------------------
# Score config
# ---------------------------------------------------------------------------

def get_score_config(game_type):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM score_config WHERE game_type=? ORDER BY placement",
            [game_type]).fetchall()]


def get_score_config_all():
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM score_config ORDER BY game_type, placement").fetchall()]


def upsert_score_config(game_type, placement, points):
    with get_db() as db:
        db.execute("""
            INSERT INTO score_config (game_type, placement, points)
            VALUES (?,?,?)
            ON CONFLICT(game_type, placement) DO UPDATE SET points=excluded.points
        """, [game_type, placement, points])
        db.commit()


def delete_score_config_row(game_type, placement):
    with get_db() as db:
        db.execute(
            "DELETE FROM score_config WHERE game_type=? AND placement=?",
            [game_type, placement])
        db.commit()
