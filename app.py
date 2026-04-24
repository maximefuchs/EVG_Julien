import os
import json
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify)
from werkzeug.security import generate_password_hash, check_password_hash
import database as db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me-in-prod")

# ---------------------------------------------------------------------------
# Bootstrap DB + initial admin
# ---------------------------------------------------------------------------

def bootstrap():
    db.init_db()
    # Create initial admin from env vars if no admin exists
    if db.count_admins() == 0:
        user = os.environ.get("INITIAL_ADMIN_USER", "admin")
        pwd  = os.environ.get("INITIAL_ADMIN_PASSWORD", "evg2025")
        db.add_admin(user, generate_password_hash(pwd))
        print(f"[EVG] Admin initial créé : {user}")

bootstrap()

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
    day = request.args.get("jour")  # samedi / dimanche / None
    leaderboard = db.get_leaderboard(day if day in ("samedi", "dimanche") else None)
    # Add rank considering ties
    leaderboard = _add_ranks(leaderboard)
    return render_template("index.html", leaderboard=leaderboard, jour=day or "tous")


@app.route("/api/leaderboard")
def api_leaderboard():
    day = request.args.get("jour")
    leaderboard = db.get_leaderboard(day if day in ("samedi", "dimanche") else None)
    leaderboard = _add_ranks(leaderboard)
    return jsonify(leaderboard)


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


@app.route("/admin/deconnexion")
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
    return render_template("admin/dashboard.html",
                           top5=top5, games=games, en_cours=en_cours,
                           total_players=total_players)


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
                try:
                    db.add_admin(username, generate_password_hash(password))
                    flash(f"Compte « {username} » créé.", "success")
                except Exception:
                    flash("Ce nom d'utilisateur existe déjà.", "danger")
        elif action == "supprimer":
            aid = int(request.form.get("admin_id"))
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
    samedi   = [g for g in games if g["day"] == "samedi"]
    dimanche = [g for g in games if g["day"] == "dimanche"]
    return render_template("admin/jeux.html", samedi=samedi, dimanche=dimanche)


@app.route("/admin/jeux/nouveau", methods=["POST"])
@login_required
def admin_jeux_nouveau():
    name      = request.form.get("name", "").strip()
    day       = request.form.get("day")
    game_type = request.form.get("type")
    if not name or day not in ("samedi", "dimanche") or game_type not in ("mini_jeu", "karting"):
        flash("Données invalides.", "danger")
        return redirect(url_for("admin_jeux"))
    game_id = db.create_game(name, day, game_type)
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

    db.save_teams(game_id, teams_data)
    # Move status to en_cours if still en_attente
    if game["status"] == "en_attente":
        db.update_game_status(game_id, "en_cours")
    flash("Équipes sauvegardées.", "success")
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

    placements = {}
    for team in teams:
        val = request.form.get(f"placement_{team['id']}", "").strip()
        if not val.isdigit() or int(val) < 1:
            flash("Tous les placements doivent être des nombres entiers ≥ 1.", "danger")
            return redirect(url_for("admin_jeu_detail", game_id=game_id))
        placements[team["id"]] = int(val)

    db.save_results(game_id, placements)
    flash("Résultats enregistrés. Le leaderboard a été mis à jour.", "success")
    return redirect(url_for("admin_jeu_detail", game_id=game_id))


@app.route("/admin/jeux/<int:game_id>/statut", methods=["POST"])
@login_required
def admin_jeu_statut(game_id):
    status = request.form.get("status")
    if status not in ("en_attente", "en_cours", "termine"):
        flash("Statut invalide.", "danger")
    else:
        db.update_game_status(game_id, status)
        flash("Statut mis à jour.", "success")
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
            if game_type not in ("mini_jeu", "karting"):
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
            if game_type in ("mini_jeu", "karting") and str(placement).isdigit():
                db.delete_score_config_row(game_type, int(placement))
                flash("Ligne supprimée.", "success")

        return redirect(url_for("admin_configuration"))

    mini_cfg    = db.get_score_config("mini_jeu")
    karting_cfg = db.get_score_config("karting")
    return render_template("admin/configuration.html",
                           mini_cfg=mini_cfg, karting_cfg=karting_cfg)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
