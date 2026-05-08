# EVG — Suivi de score & Jeux

Application web pour suivre le classement d'un week-end EVG.  
Les joueurs s'affrontent dans des mini jeux (par équipes ou individuels) et une course de karting. Les scores sont individuels et mis à jour en temps réel.

L'app embarque également un **jeu de devinette de joueur NBA** (style Poeltl) jouable en groupe.

## Fonctionnalités

### Jeux & scores
- Trois types de jeux : **Mini jeu par équipes**, **Mini jeu individuel**, **Karting**
- Pour les jeux individuels et le karting, les participants sont créés automatiquement au démarrage du jeu (un par joueur)
- Possibilité de marquer un joueur/équipe comme **N'a pas participé** — ces entrées n'affectent pas le leaderboard
- Ajustement des points par joueur/équipe via boutons **+/−** au moment de la saisie des résultats (valeur par défaut issue de la configuration)
- Leaderboard public avec auto-actualisation (30 s), filtrable par jour
- Détail des points par joueur et par jeu
- Table de points configurable séparément pour les trois types de jeux (placement → points)

### Jeu NBA — Devine le joueur
Jeu de devinette inspiré de [Poeltl](https://poeltl.nbpa.com/), jouable en groupe autour d'un seul écran.

- L'admin saisit le nom d'un joueur NBA actif → l'API NBA récupère ses données (équipe, conférence, division, poste, numéro, taille, âge)
- Les participants proposent des noms à voix haute, l'opérateur les tape dans l'interface
- Chaque devinette affiche un retour coloré colonne par colonne :
  - **Vert** — correspondance exacte
  - **Jaune** — correspondance partielle (même conférence pour l'équipe/division ; poste qui se chevauche)
  - **Rouge** — pas de correspondance ; les colonnes numériques (numéro, taille, âge) affichent une flèche **↑/↓** indiquant si le joueur mystère est plus grand/plus petit
- Devinettes illimitées ; l'état du jeu est en mémoire (remis à zéro au redémarrage du serveur)
- L'admin peut réinitialiser le jeu et choisir un nouveau joueur à tout moment

### Admin
- Portail admin protégé par mot de passe avec CSRF sur tous les formulaires
- Gestion des joueurs — l'ajout d'un nouveau joueur après des jeux terminés le marque automatiquement comme « N'a pas participé » dans ces jeux
- Gestion des jeux et équipes, avec validation (chaque équipe doit avoir au moins un joueur)
- Gestion des comptes administrateurs (création / suppression)
- Configuration du jeu NBA (choix du joueur mystère, réinitialisation)

### UX
- Lors de la saisie des résultats, les placements déjà attribués disparaissent des autres listes déroulantes
- Lors de la composition des équipes, sélectionner un joueur dans une équipe le retire des autres
- En cas d'erreur de validation, toutes les données saisies sont conservées
- Focus automatique sur le champ de saisie de la page Joueurs pour enchaîner les ajouts rapidement
- Autocomplete avec navigation clavier sur toutes les saisies de joueurs NBA

## Stack

| Couche | Technologie |
|---|---|
| Backend | Python / Flask |
| Base de données | SQLite (scores) + mémoire (jeu NBA) |
| Données NBA | `nba_api` → stats.nba.com |
| Frontend | HTML + CSS + JavaScript (vanilla) |
| Style | Bootstrap 5 (thème sombre personnalisé) |

## Lancer en local

```bash
# 1. Installer uv (si absent)
pip install uv

# 2. Installer les dépendances dans un virtualenv géré par uv
uv sync

# 3. Configurer les variables d'environnement
cp .env.example .env
# Éditer .env et renseigner SECRET_KEY, INITIAL_ADMIN_USER, INITIAL_ADMIN_PASSWORD

# 4. Lancer
uv run python app.py
```

L'app est disponible sur `http://localhost:5000`.  
Le rechargement automatique est activé avec `FLASK_DEBUG=1` dans le `.env`.

> Le jeu NBA nécessite un accès réseau vers `stats.nba.com` pour chaque lookup de joueur (~1-2 s par requête). La liste des joueurs actifs est chargée depuis les données statiques de `nba_api` (sans appel réseau).

## Variables d'environnement

Copier `.env.example` vers `.env` et renseigner toutes les valeurs.  
**Ne jamais committer `.env`** (déjà dans `.gitignore`).

| Variable | Description | Obligatoire |
|---|---|---|
| `SECRET_KEY` | Clé secrète Flask pour signer les sessions. Générer avec `python3 -c "import secrets; print(secrets.token_hex(32))"` | Oui |
| `INITIAL_ADMIN_USER` | Nom du premier compte admin créé au démarrage | Oui |
| `INITIAL_ADMIN_PASSWORD` | Mot de passe du premier compte admin (min. 8 caractères) | Oui |
| `DATABASE_PATH` | Chemin vers le fichier SQLite (défaut : `evg.db`) | Non |
| `FLASK_DEBUG` | Mettre à `1` pour activer le rechargement auto en développement | Non |

> Le compte admin initial est créé uniquement si aucun admin n'existe en base. Pour changer le mot de passe par la suite, utiliser l'interface `/admin/comptes`.

## Sécurité

- Pas de secrets hardcodés — l'application refuse de démarrer si `SECRET_KEY` ou `INITIAL_ADMIN_PASSWORD` sont absents
- Protection CSRF sur tous les formulaires POST (Flask-WTF) ; l'endpoint JSON `/nba/devine` est explicitement exempté (données non sensibles)
- Déconnexion via POST (immunisée contre les attaques CSRF de logout)
- Mots de passe hashés (Werkzeug PBKDF2)
- Longueur minimale des mots de passe admin vérifiée côté serveur (8 caractères)
- Requêtes SQL entièrement paramétrées (pas d'interpolation de chaînes)

## Déploiement sur Render

1. Pousser ce repo sur GitHub
2. Sur [render.com](https://render.com) → **New Web Service** → connecter le repo
3. Render détecte automatiquement `render.yaml` (`SECRET_KEY` est auto-généré)
4. Dans **Environment** → définir manuellement `INITIAL_ADMIN_USER` et `INITIAL_ADMIN_PASSWORD`
5. Déployer — une URL publique est générée automatiquement

> **Note :** La base SQLite est stockée dans le container Render et réinitialisée à chaque redéploiement. L'état du jeu NBA est en mémoire et donc également perdu. Pour un usage long terme des scores, migrer vers PostgreSQL.

## Structure du projet

```
app.py                    Routes Flask + logique métier
database.py               Initialisation SQLite + toutes les requêtes DB
nba_game.py               Jeu NBA : mapping équipes, fetch API, comparaison, état en mémoire
requirements.txt          Dépendances Python
pyproject.toml            Configuration uv / projet Python
.env.example              Modèle de configuration locale
Procfile                  Commande de démarrage (Render / Heroku)
render.yaml               Configuration Render
static/
  style.css               Thème sombre (variables CSS + overrides Bootstrap + styles NBA)
  script.js               Auto-refresh leaderboard + team builder JS
templates/
  base.html               Layout public (navbar avec lien NBA)
  index.html              Leaderboard
  joueur_detail.html      Détail d'un joueur
  nba/
    jeu.html              Jeu NBA public (autocomplete + tableau de devinettes)
  admin/
    base_admin.html       Layout admin (sidebar + CSRF + injection JS)
    connexion.html        Login
    dashboard.html        Tableau de bord
    joueurs.html          Gestion des joueurs
    comptes.html          Gestion des comptes admin
    jeux.html             Liste des jeux
    jeu_detail.html       Équipes + résultats
    configuration.html    Points par placement (3 types de jeux)
    nba_setup.html        Configuration du jeu NBA (choix joueur, reset)
```

## Flux d'utilisation type

### Suivi de scores
1. **Avant le week-end** — `/admin/joueurs` → ajouter tous les participants
2. **Optionnel** — `/admin/configuration` → ajuster les points par placement pour chaque type de jeu
3. **Avant chaque jeu** — `/admin/jeux` → créer le jeu (type + jour), assigner les joueurs aux équipes (mini jeu par équipes) ou démarrer directement (individuel / karting)
4. **Après chaque jeu** — saisir les placements, ajuster les points si besoin, cocher les absents → enregistrer
5. **N'importe qui** peut suivre le classement en temps réel sur l'URL publique

### Jeu NBA
1. **Admin** → `/admin/nba/` → taper un nom de joueur NBA → sélectionner dans l'autocomplete → **Définir comme joueur mystère**
2. **Tout le monde** accède à `/nba/` (lien dans la navbar)
3. **Un opérateur** tape les noms proposés à voix haute par les participants
4. Le tableau se met à jour en temps réel après chaque devinette, sans rechargement de page
5. **Admin** → `/admin/nba/` → **Réinitialiser** pour une nouvelle partie
