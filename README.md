# EVG — Suivi de score

Application web pour suivre le classement d'un week-end EVG.  
Les joueurs s'affrontent dans des mini jeux et une course de karting finale. Les scores sont individuels et mis à jour en temps réel.

## Fonctionnalités

- Leaderboard public avec auto-actualisation (30s), filtrable par jour
- Détail des points par joueur et par jeu
- Portail admin protégé par mot de passe
- Gestion des joueurs, des jeux et des équipes (les équipes changent à chaque jeu)
- Table de points configurable séparément pour les mini jeux et le karting
- Déploiement simple sur [Render](https://render.com)

## Stack

| Couche | Technologie |
|---|---|
| Backend | Python / Flask |
| Base de données | SQLite |
| Frontend | HTML + CSS + JavaScript (vanilla) |
| Style | Bootstrap 5 |

## Lancer en local

```bash
# 1. Créer et activer un virtualenv (optionnel mais recommandé)
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS / Linux

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer
python app.py
```

L'app est disponible sur `http://localhost:5000`.

### Compte admin par défaut

| Variable d'env | Valeur par défaut |
|---|---|
| `INITIAL_ADMIN_USER` | `admin` |
| `INITIAL_ADMIN_PASSWORD` | `evg2025` |

Le compte est créé automatiquement au premier démarrage si aucun admin n'existe en base.  
**Changer le mot de passe en production.**

## Variables d'environnement

| Variable | Description |
|---|---|
| `SECRET_KEY` | Clé secrète Flask pour les sessions. Obligatoire en production. |
| `INITIAL_ADMIN_USER` | Nom du premier compte admin (défaut : `admin`) |
| `INITIAL_ADMIN_PASSWORD` | Mot de passe du premier compte admin (défaut : `evg2025`) |
| `DATABASE_PATH` | Chemin vers le fichier SQLite (défaut : `evg.db`) |
| `FLASK_DEBUG` | Mettre à `1` pour activer le mode debug (dev uniquement) |

## Déploiement sur Render

1. Pousser ce repo sur GitHub
2. Sur [render.com](https://render.com) → **New Web Service** → connecter le repo
3. Render détecte automatiquement `render.yaml`
4. Dans **Environment** → définir `INITIAL_ADMIN_PASSWORD` (et optionnellement `INITIAL_ADMIN_USER`)
5. Déployer — une URL publique est générée automatiquement

> **Note :** La base SQLite est stockée dans le container Render. Elle est réinitialisée à chaque redéploiement. Pour un usage long terme, migrer vers PostgreSQL.

## Structure du projet

```
app.py                    Routes Flask + logique
database.py               Initialisation SQLite + requêtes
requirements.txt
Procfile                  Commande de démarrage pour Render
render.yaml               Configuration Render
static/
  style.css               Thème sombre
  script.js               Auto-refresh leaderboard + team builder
templates/
  base.html               Layout public
  index.html              Leaderboard
  joueur_detail.html      Détail d'un joueur
  admin/
    base_admin.html       Layout admin
    connexion.html        Login
    dashboard.html        Tableau de bord
    joueurs.html          Gestion des joueurs
    comptes.html          Gestion des comptes admin
    jeux.html             Liste des jeux
    jeu_detail.html       Équipes + résultats
    configuration.html    Points par placement
```

## Flux d'utilisation type

1. **Avant le week-end** — `/admin/joueurs` → ajouter les participants
2. **Optionnel** — `/admin/configuration` → ajuster les points par placement
3. **Avant chaque jeu** — `/admin/jeux` → créer le jeu, assigner les joueurs aux équipes
4. **Après chaque jeu** — enregistrer les placements → le leaderboard se met à jour
5. **N'importe qui** peut suivre le classement en temps réel sur l'URL publique
