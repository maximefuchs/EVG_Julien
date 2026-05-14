import os
import json
import shutil
import tempfile
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, send_file)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import database as db
import nba_game

load_dotenv()  # Load .env in development (no-op in production if vars already set)

app = Flask(__name__)

_secret = os.environ.get("SECRET_KEY")
if not _secret:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "Copy .env.example to .env and fill in the values."
    )
app.secret_key = _secret

csrf = CSRFProtect(app)

# ---------------------------------------------------------------------------
# Bootstrap DB + initial admin
# ---------------------------------------------------------------------------

def bootstrap():
    db.init_db()
    # Create initial admin from env vars if no admin exists
    if db.count_admins() == 0:
        user = os.environ.get("INITIAL_ADMIN_USER", "admin")
        pwd  = os.environ.get("INITIAL_ADMIN_PASSWORD")
        if not pwd:
            raise RuntimeError(
                "INITIAL_ADMIN_PASSWORD environment variable is not set. "
                "Set it in .env before the first run."
            )
        db.add_admin(user, generate_password_hash(pwd))
        print(f"[EVG] Admin initial créé : {user}")

bootstrap()

# ---------------------------------------------------------------------------
# Presets helper
# ---------------------------------------------------------------------------

def load_presets():
    """Load player and team-distribution presets from presets.json."""
    path = os.path.join(os.path.dirname(__file__), "presets.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin_connexion"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    leaderboard   = _add_ranks(db.get_leaderboard())
    visible_games = db.get_all_visible_games()
    game_scores   = db.get_all_game_scores()
    return render_template("index.html",
                           leaderboard=leaderboard,
                           finished_games=visible_games,
                           game_scores=game_scores)


@app.route("/api/leaderboard")
def api_leaderboard():
    leaderboard   = _add_ranks(db.get_leaderboard())
    visible_games = db.get_all_visible_games()
    game_scores   = db.get_all_game_scores()
    # Embed per-game scores into each leaderboard entry (JSON keys must be strings)
    for entry in leaderboard:
        entry["game_scores"] = {
            str(gid): pts
            for gid, pts in game_scores.get(entry["id"], {}).items()
        }
    return jsonify({"leaderboard": leaderboard, "games": visible_games})


@app.route("/joueur/<int:player_id>")
def joueur_detail(player_id):
    players = db.get_all_players()
    player = next((p for p in players if p["id"] == player_id), None)
    if not player:
        flash("Joueur introuvable.", "danger")
        return redirect(url_for("index"))
    breakdown = db.get_player_game_breakdown(player_id)
    total = sum(b["points"] for b in breakdown)
    return render_template("joueur_detail.html",
                           player=player, breakdown=breakdown, total=total)


def _add_ranks(leaderboard):
    rank = 1
    for i, entry in enumerate(leaderboard):
        if i == 0:
            entry["rank"] = 1
        elif entry["total_points"] == leaderboard[i - 1]["total_points"]:
            entry["rank"] = leaderboard[i - 1]["rank"]
        else:
            entry["rank"] = i + 1
    return leaderboard


# ---------------------------------------------------------------------------
# Admin – Auth
# ---------------------------------------------------------------------------

@app.route("/admin/connexion", methods=["GET", "POST"])
def admin_connexion():
    if "admin_id" in session:
        return redirect(url_for("admin_dashboard"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = db.get_admin_by_username(username)
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            return redirect(url_for("admin_dashboard"))
        error = "Identifiants incorrects."
    return render_template("admin/connexion.html", error=error)


@app.route("/admin/deconnexion", methods=["POST"])
def admin_deconnexion():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Admin – Dashboard
# ---------------------------------------------------------------------------

@app.route("/admin/")
@login_required
def admin_dashboard():
    leaderboard = _add_ranks(db.get_leaderboard())
    top5 = leaderboard[:5]
    games = db.get_all_games()
    en_cours = [g for g in games if g["status"] == "en_cours"]
    total_players = len(db.get_all_players())
    finished_games = db.get_finished_games_with_results()
    ongoing_games  = db.get_ongoing_games_with_results()
    return render_template("admin/dashboard.html",
                           top5=top5, games=games, en_cours=en_cours,
                           total_players=total_players,
                           finished_games=finished_games,
                           ongoing_games=ongoing_games)


# ---------------------------------------------------------------------------
# Admin – Joueurs
# ---------------------------------------------------------------------------

@app.route("/admin/joueurs", methods=["GET", "POST"])
@login_required
def admin_joueurs():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "ajouter":
            name = request.form.get("name", "").strip()
            if name:
                try:
                    db.add_player(name)
                    # Get the newly created player and mark them as dnp in all finished games
                    all_players = db.get_all_players()
                    new_player = next((p for p in all_players if p["name"] == name), None)
                    if new_player:
                        db.mark_new_player_dnp_in_finished_games(new_player["id"])
                    flash(f"Joueur « {name} » ajouté.", "success")
                except Exception:
                    flash("Ce nom existe déjà.", "danger")
        elif action == "renommer":
            pid  = request.form.get("player_id")
            name = request.form.get("name", "").strip()
            if pid and name:
                try:
                    db.rename_player(int(pid), name)
                    flash("Joueur renommé.", "success")
                except Exception:
                    flash("Ce nom existe déjà.", "danger")
        elif action == "supprimer":
            pid = request.form.get("player_id")
            if pid:
                db.delete_player(int(pid))
                flash("Joueur supprimé.", "success")
        return redirect(url_for("admin_joueurs"))

    players = db.get_all_players()
    return render_template("admin/joueurs.html", players=players)


# ---------------------------------------------------------------------------
# Admin – Comptes
# ---------------------------------------------------------------------------

@app.route("/admin/comptes", methods=["GET", "POST"])
@login_required
def admin_comptes():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "ajouter":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if username and password:
                if len(password) < 8:
                    flash("Le mot de passe doit faire au moins 8 caractères.", "danger")
                    return redirect(url_for("admin_comptes"))
                try:
                    db.add_admin(username, generate_password_hash(password))
                    flash(f"Compte « {username} » créé.", "success")
                except Exception:
                    flash("Ce nom d'utilisateur existe déjà.", "danger")
        elif action == "supprimer":
            try:
                aid = int(request.form.get("admin_id", ""))
            except (ValueError, TypeError):
                flash("Identifiant invalide.", "danger")
                return redirect(url_for("admin_comptes"))
            if aid == session["admin_id"]:
                flash("Vous ne pouvez pas supprimer votre propre compte.", "danger")
            elif db.count_admins() <= 1:
                flash("Impossible de supprimer le dernier compte admin.", "danger")
            else:
                db.delete_admin(aid)
                flash("Compte supprimé.", "success")
        return redirect(url_for("admin_comptes"))

    admins = db.get_all_admins()
    return render_template("admin/comptes.html", admins=admins)


# ---------------------------------------------------------------------------
# Admin – Jeux (liste)
# ---------------------------------------------------------------------------

@app.route("/admin/jeux")
@login_required
def admin_jeux():
    games = db.get_all_games()
    return render_template("admin/jeux.html", games=games)


@app.route("/admin/jeux/nouveau", methods=["POST"])
@login_required
def admin_jeux_nouveau():
    name      = request.form.get("name", "").strip()
    game_type = request.form.get("type")
    if not name or game_type not in ("mini_jeu", "karting", "mini_jeu_ind", "bonus"):
        flash("Données invalides.", "danger")
        return redirect(url_for("admin_jeux"))
    game_id = db.create_game(name, game_type)
    flash(f"Jeu « {name} » créé.", "success")
    return redirect(url_for("admin_jeu_detail", game_id=game_id))


# ---------------------------------------------------------------------------
# Admin – Jeu détail
# ---------------------------------------------------------------------------

@app.route("/admin/jeux/<int:game_id>")
@login_required
def admin_jeu_detail(game_id):
    game = db.get_game(game_id)
    if not game:
        flash("Jeu introuvable.", "danger")
        return redirect(url_for("admin_jeux"))
    teams   = db.get_teams_for_game(game_id)
    players = db.get_all_players()
    free_players = db.get_players_not_in_game(game_id)
    if game["type"] == "bonus":
        n = len(teams)
        score_cfg = [{"placement": k, "points": n + 1 - 2 * k} for k in range(1, n + 1)]
    else:
        score_cfg = db.get_score_config(game["type"])
    return render_template("admin/jeu_detail.html",
                           game=game, teams=teams,
                           players=players, free_players=free_players,
                           score_cfg=score_cfg)


@app.route("/admin/jeux/<int:game_id>/equipes", methods=["POST"])
@login_required
def admin_jeu_equipes(game_id):
    game = db.get_game(game_id)
    if not game:
        flash("Jeu introuvable.", "danger")
        return redirect(url_for("admin_jeux"))
    if game["status"] == "termine":
        flash("Ce jeu est terminé, les équipes ne peuvent plus être modifiées.", "warning")
        return redirect(url_for("admin_jeu_detail", game_id=game_id))

    # Parse teams from form: team_name_1, team_players_1[], team_name_2, ...
    teams_data = []
    i = 1
    while True:
        team_name = request.form.get(f"team_name_{i}", "").strip()
        if not team_name:
            break
        raw_ids = request.form.getlist(f"team_players_{i}[]")
        player_ids = [int(pid) for pid in raw_ids if pid]
        teams_data.append({"name": team_name, "player_ids": player_ids})
        i += 1

    if not teams_data:
        flash("Aucune équipe fournie.", "warning")
        return redirect(url_for("admin_jeu_detail", game_id=game_id))

    error_team = next((t for t in teams_data if not t["player_ids"]), None)
    if error_team:
        flash(f"L'équipe « {error_team['name']} » doit avoir au moins un joueur.", "danger")
        # Reconstruct teams in template shape so the form is preserved
        all_players = db.get_all_players()
        player_map = {p["id"]: p for p in all_players}
        fake_teams = []
        for idx, t in enumerate(teams_data):
            fake_teams.append({
                "id": None,
                "name": t["name"],
                "placement": None,
                "points_override": None,
                "did_not_participate": 0,
                "players": [player_map[pid] for pid in t["player_ids"] if pid in player_map],
            })
        score_cfg = db.get_score_config(game["type"])
        free_players = [p for p in all_players
                        if p["id"] not in {pid for t in teams_data for pid in t["player_ids"]}]
        return render_template("admin/jeu_detail.html",
                               game=game, teams=[],
                               form_teams=fake_teams,
                               players=all_players, free_players=free_players,
                               score_cfg=score_cfg)

    db.save_teams(game_id, teams_data)
    # Move status to en_cours if still en_attente
    if game["status"] == "en_attente":
        db.update_game_status(game_id, "en_cours")
    flash("Équipes sauvegardées.", "success")
    return redirect(url_for("admin_jeu_detail", game_id=game_id))


@app.route("/admin/jeux/<int:game_id>/participants", methods=["POST"])
@login_required
def admin_jeu_participants(game_id):
    game = db.get_game(game_id)
    if not game or game["type"] != "bonus":
        flash("Jeu introuvable ou type incorrect.", "danger")
        return redirect(url_for("admin_jeux"))
    if game["status"] == "termine":
        flash("Ce jeu est terminé, les participants ne peuvent plus être modifiés.", "warning")
        return redirect(url_for("admin_jeu_detail", game_id=game_id))

    raw_ids = request.form.getlist("player_ids[]")
    player_ids = [int(pid) for pid in raw_ids if pid.isdigit()]

    if len(player_ids) < 2:
        flash("Sélectionnez au moins 2 participants.", "warning")
        return redirect(url_for("admin_jeu_detail", game_id=game_id))

    db.setup_bonus_game(game_id, player_ids)
    if game["status"] == "en_attente":
        db.update_game_status(game_id, "en_cours")
    flash("Participants sauvegardés.", "success")
    return redirect(url_for("admin_jeu_detail", game_id=game_id))


@app.route("/admin/jeux/<int:game_id>/resultats", methods=["POST"])
@login_required
def admin_jeu_resultats(game_id):
    game = db.get_game(game_id)
    if not game:
        flash("Jeu introuvable.", "danger")
        return redirect(url_for("admin_jeux"))

    teams = db.get_teams_for_game(game_id)
    if not teams:
        flash("Aucune équipe enregistrée pour ce jeu.", "warning")
        return redirect(url_for("admin_jeu_detail", game_id=game_id))

    # Determine whether this is a temporary save or a final finish
    finish = request.form.get("action", "finish") == "finish"

    placements = {}
    overrides = {}
    dnp_team_ids = set()
    error = None
    for team in teams:
        dnp = request.form.get(f"dnp_{team['id']}") == "1"
        if dnp:
            dnp_team_ids.add(team["id"])
            continue
        val = request.form.get(f"placement_{team['id']}", "").strip()
        if val.isdigit() and int(val) >= 1:
            placements[team["id"]] = int(val)
        elif finish:
            # Strict validation only when finishing the game
            error = f"Le placement de « {team['name']} » est invalide (doit être ≥ 1, ou cochez N'a pas participé)."
            break
        # For save without a placement: leave the team unranked (NULL) — no error
        ov = request.form.get(f"points_override_{team['id']}", "").strip()
        overrides[team["id"]] = int(ov) if ov.lstrip("-").isdigit() else None

    # When finishing, validate that rank sequence is logically consistent:
    # ranks must start at 1, and after k participants sharing rank r the next
    # distinct rank must be exactly r + k  (standard competition ranking).
    if finish and not error and placements:
        rank_values = sorted(placements.values())
        if rank_values[0] != 1:
            error = "Le classement doit commencer à la 1re place."
        else:
            i = 0
            while i < len(rank_values) and not error:
                current_rank = rank_values[i]
                j = i
                while j < len(rank_values) and rank_values[j] == current_rank:
                    j += 1
                count = j - i          # how many share this rank
                if j < len(rank_values) and rank_values[j] != current_rank + count:
                    error = (
                        f"Classement invalide : {count} participant(s) sont à la "
                        f"{current_rank}e place, donc la prochaine doit être la "
                        f"{current_rank + count}e (pas la {rank_values[j]}e)."
                    )
                i = j

    if error:
        # Re-inject submitted values into teams so the form keeps what was typed
        for team in teams:
            team["placement"] = placements.get(team["id"], team.get("placement"))
            team["points_override"] = overrides.get(team["id"], team.get("points_override"))
            team["did_not_participate"] = 1 if team["id"] in dnp_team_ids else 0
        flash(error, "danger")
        if game["type"] == "bonus":
            n = len(teams)
            score_cfg = [{"placement": k, "points": n + 1 - 2 * k} for k in range(1, n + 1)]
        else:
            score_cfg = db.get_score_config(game["type"])
        players = db.get_all_players()
        free_players = db.get_players_not_in_game(game_id)
        return render_template("admin/jeu_detail.html",
                               game=game, teams=teams,
                               players=players, free_players=free_players,
                               score_cfg=score_cfg)

    db.save_results(game_id, placements, overrides, dnp_team_ids, finish=finish)
    if finish:
        flash("Résultats enregistrés. Le jeu est terminé.", "success")
    else:
        flash("Scores sauvegardés.", "success")
    return redirect(url_for("admin_jeu_detail", game_id=game_id))


@app.route("/admin/jeux/<int:game_id>/statut", methods=["POST"])
@login_required
def admin_jeu_statut(game_id):
    status = request.form.get("status")
    if status not in ("en_attente", "en_cours", "termine"):
        flash("Statut invalide.", "danger")
    else:
        game = db.get_game(game_id)
        db.update_game_status(game_id, status)
        # For individual games, auto-create one entry per player when starting
        if status == "en_cours" and game and game["type"] in ("mini_jeu_ind", "karting"):
            db.setup_individual_game(game_id)
        flash("Statut mis à jour.", "success")
    return redirect(url_for("admin_jeu_detail", game_id=game_id))


@app.route("/admin/jeux/<int:game_id>/renommer", methods=["POST"])
@login_required
def admin_jeu_renommer(game_id):
    game = db.get_game(game_id)
    if not game:
        flash("Jeu introuvable.", "danger")
        return redirect(url_for("admin_jeux"))
    new_name = request.form.get("name", "").strip()
    if not new_name:
        flash("Le nom ne peut pas être vide.", "warning")
        return redirect(url_for("admin_jeu_detail", game_id=game_id))
    db.rename_game(game_id, new_name)
    flash(f"Jeu renommé en « {new_name} ».", "success")
    return redirect(url_for("admin_jeu_detail", game_id=game_id))


@app.route("/admin/jeux/<int:game_id>/supprimer", methods=["POST"])
@login_required
def admin_jeu_supprimer(game_id):
    game = db.get_game(game_id)
    if game and game["status"] == "termine":
        flash("Un jeu terminé ne peut pas être supprimé.", "danger")
        return redirect(url_for("admin_jeu_detail", game_id=game_id))
    db.delete_game(game_id)
    flash("Jeu supprimé.", "success")
    return redirect(url_for("admin_jeux"))


# ---------------------------------------------------------------------------
# Admin – Configuration des points
# ---------------------------------------------------------------------------

@app.route("/admin/configuration", methods=["GET", "POST"])
@login_required
def admin_configuration():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "sauvegarder":
            game_type = request.form.get("game_type")
            if game_type not in ("mini_jeu", "karting", "mini_jeu_ind"):
                flash("Type de jeu invalide.", "danger")
                return redirect(url_for("admin_configuration"))
            placements = request.form.getlist("placement[]")
            points_list = request.form.getlist("points[]")
            for p, pts in zip(placements, points_list):
                if p.isdigit() and pts.lstrip("-").isdigit():
                    db.upsert_score_config(game_type, int(p), int(pts))
            flash("Configuration sauvegardée.", "success")

        elif action == "supprimer_ligne":
            game_type = request.form.get("game_type")
            placement = request.form.get("placement")
            if game_type in ("mini_jeu", "karting", "mini_jeu_ind") and str(placement).isdigit():
                db.delete_score_config_row(game_type, int(placement))
                flash("Ligne supprimée.", "success")

        return redirect(url_for("admin_configuration"))

    mini_cfg    = db.get_score_config("mini_jeu")
    karting_cfg = db.get_score_config("karting")
    ind_cfg     = db.get_score_config("mini_jeu_ind")
    return render_template("admin/configuration.html",
                           mini_cfg=mini_cfg, karting_cfg=karting_cfg, ind_cfg=ind_cfg)


# ---------------------------------------------------------------------------
# Admin – Reset database
# ---------------------------------------------------------------------------

@app.route("/admin/reset", methods=["GET", "POST"])
@login_required
def admin_reset():
    if request.method == "POST":
        confirmation = request.form.get("confirmation", "").strip()
        if confirmation != "RESET":
            flash("Confirmation incorrecte. Tapez exactement RESET.", "danger")
            return redirect(url_for("admin_reset"))
        db.reset_db()
        flash("Base de données réinitialisée. Tous les joueurs, jeux et scores ont été supprimés.", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/reset.html")


# ---------------------------------------------------------------------------
# Admin – Export / Import database
# ---------------------------------------------------------------------------

@app.route("/admin/db/export")
@login_required
def admin_db_export():
    db_path = db.DATABASE
    # Copy to a temp file so the download name is always "evg_backup.db"
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    shutil.copy2(db_path, tmp.name)
    return send_file(tmp.name, as_attachment=True, download_name="evg_backup.db",
                     mimetype="application/octet-stream")


@app.route("/admin/db/import", methods=["GET", "POST"])
@login_required
def admin_db_import():
    if request.method == "POST":
        f = request.files.get("db_file")
        if not f or not f.filename.endswith(".db"):
            flash("Fichier invalide. Choisissez un fichier .db.", "danger")
            return redirect(url_for("admin_db_import"))
        # Write directly over the live database file
        f.save(db.DATABASE)
        # Re-run migrations in case the backup is from an older schema
        db.init_db()
        flash("Base de données restaurée avec succès.", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/db_import.html")


# ---------------------------------------------------------------------------
# Admin – Préréglages
# ---------------------------------------------------------------------------

@app.route("/admin/presets")
@login_required
def admin_presets():
    presets = load_presets()
    existing_names = {p["name"] for p in db.get_all_players()}
    missing_players = [name for name in presets["players"] if name not in existing_names]
    return render_template("admin/presets.html",
                           presets=presets,
                           existing_names=existing_names,
                           missing_players=missing_players)


@app.route("/admin/presets/joueurs", methods=["POST"])
@login_required
def admin_presets_joueurs():
    presets = load_presets()
    existing_names = {p["name"] for p in db.get_all_players()}
    added = 0
    for name in presets["players"]:
        if name not in existing_names:
            db.add_player(name)
            all_players = db.get_all_players()
            new_player = next((p for p in all_players if p["name"] == name), None)
            if new_player:
                db.mark_new_player_dnp_in_finished_games(new_player["id"])
            added += 1
    if added:
        flash(f"{added} joueur(s) ajouté(s).", "success")
    else:
        flash("Tous les joueurs prédéfinis sont déjà présents.", "info")
    return redirect(url_for("admin_presets"))


@app.route("/admin/presets/equipes", methods=["POST"])
@login_required
def admin_presets_equipes():
    presets = load_presets()
    game_name = request.form.get("game_name", "").strip()
    try:
        dist_idx = int(request.form.get("distribution_index", ""))
        distribution = presets["distributions"][dist_idx]
    except (ValueError, IndexError):
        flash("Répartition invalide.", "danger")
        return redirect(url_for("admin_presets"))

    if not game_name:
        flash("Le nom du jeu est requis.", "warning")
        return redirect(url_for("admin_presets"))

    player_map = {p["name"]: p["id"] for p in db.get_all_players()}
    teams_data = []
    missing = []
    for team in distribution["teams"]:
        player_ids = []
        for pname in team["players"]:
            pid = player_map.get(pname)
            if pid is None:
                missing.append(pname)
            else:
                player_ids.append(pid)
        teams_data.append({"name": team["name"], "player_ids": player_ids})

    if missing:
        flash(f"Joueurs introuvables : {', '.join(missing)}. Importez d'abord les joueurs prédéfinis.", "danger")
        return redirect(url_for("admin_presets"))

    game_id = db.create_game(game_name, "mini_jeu")
    db.save_teams(game_id, teams_data)
    db.update_game_status(game_id, "en_cours")
    flash(f"Jeu « {game_name} » créé avec la {distribution['label']}.", "success")
    return redirect(url_for("admin_jeu_detail", game_id=game_id))


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Mesures – Jeu public
# ---------------------------------------------------------------------------

@app.route("/mesures/")
def mesures_jeu():
    return render_template("mesures/jeu.html")


# ---------------------------------------------------------------------------
# NBA – Jeu public
# ---------------------------------------------------------------------------

@app.route("/nba/")
def nba_jeu():
    return render_template(
        "nba/jeu.html",
        game=nba_game.game_state,
        target_set=(nba_game.game_state["target"] is not None),
    )


@app.route("/nba/devine", methods=["POST"])
@csrf.exempt
def nba_devine():
    data = request.get_json(silent=True) or {}
    player_id = data.get("player_id")
    if not player_id:
        return jsonify({"error": "Identifiant de joueur manquant."}), 400
    if nba_game.game_state["target"] is None:
        return jsonify({"error": "Aucun joueur mystère n'est défini. Demande à l'admin de configurer le jeu."}), 400
    if nba_game.game_state["found"]:
        return jsonify({"error": "Le joueur a déjà été trouvé !"}), 400
    try:
        nba_game.add_guess(int(player_id))
        return jsonify({
            "guesses": nba_game.game_state["guesses"],
            "found":   nba_game.game_state["found"],
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/nba/joueurs")
def api_nba_joueurs():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    return jsonify(nba_game.search_players(q))


# ---------------------------------------------------------------------------
# NBA – Administration
# ---------------------------------------------------------------------------

@app.route("/admin/nba/")
@login_required
def admin_nba():
    return render_template("admin/nba_setup.html", game=nba_game.game_state)


@app.route("/admin/nba/joueur", methods=["POST"])
@login_required
def admin_nba_joueur():
    player_id = request.form.get("player_id", "").strip()
    if not player_id or not player_id.isdigit():
        flash("Sélectionne un joueur dans la liste de suggestions.", "danger")
        return redirect(url_for("admin_nba"))
    try:
        player = nba_game.set_target(int(player_id))
        flash(
            f"Joueur mystère défini : {player['name']} ({player['team_name']}). "
            "Le jeu est prêt !",
            "success",
        )
    except Exception as exc:
        flash(f"Erreur lors de la récupération des données : {exc}", "danger")
    return redirect(url_for("admin_nba"))


@app.route("/admin/nba/reset", methods=["POST"])
@login_required
def admin_nba_reset():
    nba_game.reset_game()
    flash("Jeu NBA réinitialisé.", "success")
    return redirect(url_for("admin_nba"))


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
