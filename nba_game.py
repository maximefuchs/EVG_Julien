"""
nba_game.py — Logique du jeu de devinette de joueurs NBA (style Poeltl).

Flow :
  1. L'admin appelle set_target(player_id) → récupère les données du joueur mystère.
  2. Les joueurs appellent add_guess(player_id) → compare la devinette à la cible.
  3. reset_game() remet tout à zéro.

L'état du jeu est en mémoire (perdu au redémarrage du serveur).
"""

import datetime
from nba_api.stats.static import players as nba_players
from nba_api.stats.endpoints import commonplayerinfo

# ---------------------------------------------------------------------------
# Correspondance équipe → conférence / division  (saison 2024-25)
# ---------------------------------------------------------------------------

TEAM_INFO: dict[str, dict] = {
    # Conférence Est — Division Atlantique
    "BOS": {"name": "Boston Celtics",         "conference": "Est",   "division": "Atlantique"},
    "BKN": {"name": "Brooklyn Nets",           "conference": "Est",   "division": "Atlantique"},
    "NYK": {"name": "New York Knicks",         "conference": "Est",   "division": "Atlantique"},
    "PHI": {"name": "Philadelphia 76ers",      "conference": "Est",   "division": "Atlantique"},
    "TOR": {"name": "Toronto Raptors",         "conference": "Est",   "division": "Atlantique"},
    # Conférence Est — Division Centrale
    "CHI": {"name": "Chicago Bulls",           "conference": "Est",   "division": "Centrale"},
    "CLE": {"name": "Cleveland Cavaliers",     "conference": "Est",   "division": "Centrale"},
    "DET": {"name": "Detroit Pistons",         "conference": "Est",   "division": "Centrale"},
    "IND": {"name": "Indiana Pacers",          "conference": "Est",   "division": "Centrale"},
    "MIL": {"name": "Milwaukee Bucks",         "conference": "Est",   "division": "Centrale"},
    # Conférence Est — Division Sud-Est
    "ATL": {"name": "Atlanta Hawks",           "conference": "Est",   "division": "Sud-Est"},
    "CHA": {"name": "Charlotte Hornets",       "conference": "Est",   "division": "Sud-Est"},
    "MIA": {"name": "Miami Heat",              "conference": "Est",   "division": "Sud-Est"},
    "ORL": {"name": "Orlando Magic",           "conference": "Est",   "division": "Sud-Est"},
    "WAS": {"name": "Washington Wizards",      "conference": "Est",   "division": "Sud-Est"},
    # Conférence Ouest — Division Nord-Ouest
    "DEN": {"name": "Denver Nuggets",          "conference": "Ouest", "division": "Nord-Ouest"},
    "MIN": {"name": "Minnesota Timberwolves",  "conference": "Ouest", "division": "Nord-Ouest"},
    "OKC": {"name": "Oklahoma City Thunder",   "conference": "Ouest", "division": "Nord-Ouest"},
    "POR": {"name": "Portland Trail Blazers",  "conference": "Ouest", "division": "Nord-Ouest"},
    "UTA": {"name": "Utah Jazz",               "conference": "Ouest", "division": "Nord-Ouest"},
    # Conférence Ouest — Division Pacifique
    "GSW": {"name": "Golden State Warriors",   "conference": "Ouest", "division": "Pacifique"},
    "LAC": {"name": "LA Clippers",             "conference": "Ouest", "division": "Pacifique"},
    "LAL": {"name": "Los Angeles Lakers",      "conference": "Ouest", "division": "Pacifique"},
    "PHX": {"name": "Phoenix Suns",            "conference": "Ouest", "division": "Pacifique"},
    "SAC": {"name": "Sacramento Kings",        "conference": "Ouest", "division": "Pacifique"},
    # Conférence Ouest — Division Sud-Ouest
    "DAL": {"name": "Dallas Mavericks",        "conference": "Ouest", "division": "Sud-Ouest"},
    "HOU": {"name": "Houston Rockets",         "conference": "Ouest", "division": "Sud-Ouest"},
    "MEM": {"name": "Memphis Grizzlies",       "conference": "Ouest", "division": "Sud-Ouest"},
    "NOP": {"name": "New Orleans Pelicans",    "conference": "Ouest", "division": "Sud-Ouest"},
    "SAS": {"name": "San Antonio Spurs",       "conference": "Ouest", "division": "Sud-Ouest"},
}

# ---------------------------------------------------------------------------
# Normalisation des positions
# ---------------------------------------------------------------------------

_POS_MAP: dict[str, str] = {
    "guard":          "G",
    "forward":        "F",
    "center":         "C",
    "guard-forward":  "G-F",
    "forward-guard":  "F-G",
    "forward-center": "F-C",
    "center-forward": "C-F",
    "guard-center":   "G-C",
    "center-guard":   "C-G",
}


def _normalise_position(raw: str) -> str:
    key = raw.strip().lower()
    return _POS_MAP.get(key, raw.strip().upper() or "?")


def _position_components(pos: str) -> set:
    """Décompose "G-F" en {"G", "F"}."""
    return set(pos.split("-")) if pos and pos != "?" else set()


# ---------------------------------------------------------------------------
# Cache de joueurs actifs
# ---------------------------------------------------------------------------

_players_cache: list[dict] = []


def get_active_players() -> list[dict]:
    """Retourne la liste {id, full_name} de tous les joueurs NBA actifs.
    La liste est chargée une seule fois depuis les données statiques de nba_api
    (aucun appel réseau requis).
    """
    global _players_cache
    if not _players_cache:
        _players_cache = [
            {"id": p["id"], "full_name": p["full_name"]}
            for p in nba_players.get_active_players()
        ]
    return _players_cache


def search_players(query: str) -> list[dict]:
    """Retourne jusqu'à 15 joueurs dont le nom contient la requête."""
    q = query.lower()
    return [p for p in get_active_players() if q in p["full_name"].lower()][:15]


# ---------------------------------------------------------------------------
# Récupération des données d'un joueur
# ---------------------------------------------------------------------------

def _height_to_inches(h: str) -> int | None:
    """Convertit "6-9" (ou "6-09") en nombre total de pouces."""
    try:
        parts = h.split("-")
        return int(parts[0]) * 12 + int(parts[1])
    except Exception:
        return None


def _inches_to_display(inches: int | None) -> str:
    if inches is None:
        return "N/A"
    return f"{inches // 12}'{inches % 12}\""


def _calc_age(birthdate_str: str) -> int | None:
    """Calcule l'âge à partir d'une date ISO (ex: '1984-12-30T00:00:00')."""
    try:
        bd = datetime.datetime.fromisoformat(birthdate_str.split("T")[0])
        today = datetime.date.today()
        return today.year - bd.year - (
            (today.month, today.day) < (bd.month, bd.day)
        )
    except Exception:
        return None


def fetch_player_data(player_id: int) -> dict:
    """Récupère les informations détaillées d'un joueur via l'API NBA.
    Retourne un dict structuré avec tous les attributs nécessaires au jeu.
    """
    cpi = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=15)
    data = cpi.get_normalized_dict()
    d = data["CommonPlayerInfo"][0]

    team_abbr = d.get("TEAM_ABBREVIATION", "") or ""
    team_info = TEAM_INFO.get(team_abbr, {})

    height_raw = d.get("HEIGHT", "") or ""
    height_inches = _height_to_inches(height_raw)

    # Nom complet de l'équipe : TEAM_CITY + TEAM_NAME si non présent dans notre mapping
    team_name = team_info.get(
        "name",
        f"{d.get('TEAM_CITY', '')} {d.get('TEAM_NAME', '')}".strip() or "Agent libre",
    )

    return {
        "id":          player_id,
        "name":        d.get("DISPLAY_FIRST_LAST", ""),
        "team_abbr":   team_abbr,
        "team_name":   team_name,
        "conference":  team_info.get("conference", "?"),
        "division":    team_info.get("division", "?"),
        "position":    _normalise_position(d.get("POSITION", "") or ""),
        "jersey":      d.get("JERSEY", "?") or "?",
        "height_in":   height_inches,
        "height_disp": _inches_to_display(height_inches),
        "age":         _calc_age(d.get("BIRTHDATE", "") or ""),
    }


# ---------------------------------------------------------------------------
# Logique de comparaison
# ---------------------------------------------------------------------------

def _numeric_hint(guess_val: int | None, target_val: int | None) -> tuple[str, str | None]:
    """Retourne (résultat, direction) pour un attribut numérique."""
    if guess_val is None or target_val is None:
        return "rouge", None
    if guess_val == target_val:
        return "vert", None
    return "rouge", "haut" if target_val > guess_val else "bas"


def compare_players(target: dict, guess: dict) -> dict:
    """Compare la devinette à la cible joueur par joueur.

    Chaque colonne produit:
      {"value": ..., "result": "vert"|"jaune"|"rouge", "direction": "haut"|"bas"|None}

    Règles:
      Équipe     — vert=même équipe, jaune=même conférence, rouge=conférence différente
      Conférence — vert=même, rouge=différente
      Division   — vert=même, jaune=même conférence, rouge=différente
      Position   — vert=identique, jaune=chevauchement partiel, rouge=aucun
      Numéro     — vert=identique, rouge+flèche sinon
      Taille     — vert=identique, rouge+flèche sinon
      Âge        — vert=identique, rouge+flèche sinon
    """
    r: dict = {}

    # Équipe
    if guess["team_abbr"] and guess["team_abbr"] == target["team_abbr"]:
        r["equipe"] = {"value": guess["team_name"], "result": "vert",  "direction": None}
    elif guess["conference"] == target["conference"] and guess["conference"] != "?":
        r["equipe"] = {"value": guess["team_name"], "result": "jaune", "direction": None}
    else:
        r["equipe"] = {"value": guess["team_name"], "result": "rouge", "direction": None}

    # Conférence
    r["conference"] = {
        "value":     guess["conference"],
        "result":    "vert" if guess["conference"] == target["conference"] and guess["conference"] != "?" else "rouge",
        "direction": None,
    }

    # Division
    if guess["division"] == target["division"] and guess["division"] != "?":
        r["division"] = {"value": guess["division"], "result": "vert",  "direction": None}
    elif guess["conference"] == target["conference"] and guess["conference"] != "?":
        r["division"] = {"value": guess["division"], "result": "jaune", "direction": None}
    else:
        r["division"] = {"value": guess["division"], "result": "rouge", "direction": None}

    # Position
    gc = _position_components(guess["position"])
    tc = _position_components(target["position"])
    if gc and gc == tc:
        pos_res = "vert"
    elif gc & tc:
        pos_res = "jaune"
    else:
        pos_res = "rouge"
    r["position"] = {"value": guess["position"], "result": pos_res, "direction": None}

    # Numéro de maillot
    try:
        gj, tj = int(guess["jersey"]), int(target["jersey"])
        res, direction = _numeric_hint(gj, tj)
    except (ValueError, TypeError):
        res, direction = "rouge", None
    r["numero"] = {"value": guess["jersey"], "result": res, "direction": direction}

    # Taille
    res, direction = _numeric_hint(guess["height_in"], target["height_in"])
    r["taille"] = {"value": guess["height_disp"], "result": res, "direction": direction}

    # Âge
    res, direction = _numeric_hint(guess["age"], target["age"])
    r["age"] = {"value": str(guess["age"]) if guess["age"] is not None else "?", "result": res, "direction": direction}

    # Méta
    r["_correct"]      = (guess["id"] == target["id"])
    r["_player_name"]  = guess["name"]

    return r


# ---------------------------------------------------------------------------
# État en mémoire
# ---------------------------------------------------------------------------

game_state: dict = {
    "target":  None,   # dict retourné par fetch_player_data
    "guesses": [],     # list de dicts retournés par compare_players
    "found":   False,
}


def set_target(player_id: int) -> dict:
    """Définit le joueur mystère. Remet les devinettes à zéro."""
    player = fetch_player_data(player_id)
    game_state["target"]  = player
    game_state["guesses"] = []
    game_state["found"]   = False
    return player


def add_guess(player_id: int) -> dict:
    """Ajoute une devinette. Retourne le dict de comparaison."""
    if game_state["target"] is None:
        raise ValueError("Aucun joueur mystère n'est défini.")
    guess  = fetch_player_data(player_id)
    result = compare_players(game_state["target"], guess)
    game_state["guesses"].append(result)
    if result["_correct"]:
        game_state["found"] = True
    return result


def reset_game() -> None:
    """Remet le jeu à zéro."""
    game_state["target"]  = None
    game_state["guesses"] = []
    game_state["found"]   = False
