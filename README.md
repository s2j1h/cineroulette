# Ciné-Roulette

Application web personnelle de gestion d'une collection de DVD/Blu-ray : ajout par
scan de code-barre avec enrichissement automatique des métadonnées (DVDFr → TMDB →
OMDb), catégorisation par couleur, recherche, et une fonctionnalité de découverte
aléatoire ("roulette").

Usage prévu : mono-utilisateur, sur un homelab local (LXC Proxmox ou Docker),
accessible en réseau local ou via WireGuard.

> **Note** : cette application a été développée avec [Claude Code](https://claude.com/claude-code)
> et relue/vérifiée par un humain (tests fonctionnels manuels de toutes les
> routes : CRUD, recherche, filtres, roulette, scan, quota DVDFr). Comme pour
> tout code généré assisté par IA, une relecture reste recommandée avant toute
> exposition au-delà d'un usage personnel en réseau local.

## Stack

- Backend : Python 3.12 + Flask
- ORM / DB : SQLAlchemy + SQLite (fichier unique)
- Frontend : Jinja2 (rendu serveur) + CSS + JS vanilla
- Scan code-barre : [html5-qrcode](https://github.com/mebjas/html5-qrcode) (vendorisé
  localement dans `cineroulette/static/js/`, pas de dépendance CDN au runtime)
- Intégrations externes : DVDFr (identification par EAN), TMDB (métadonnées),
  OMDb (note IMDb)

Aucune authentification n'est implémentée (usage mono-utilisateur, réseau local).

## Fonctionnalités

- **Collection** (`/dvd`) : liste paginée, filtres par couleur et thème, recherche
  live par titre (FR/EN, insensible à la casse, debounce 300 ms, sans rechargement
  de page).
- **Fiche DVD** (`/dvd/<id>`) : détail complet, jaquette, modification, suppression
  (avec confirmation).
- **Ajout par scan** (`/dvd/scan`) : scan caméra de l'EAN → enrichissement
  automatique DVDFr → TMDB → OMDb → formulaire pré-rempli à valider.
- **Ajout manuel** (`/dvd/new`) : formulaire vierge, avec recherche rapide TMDB par
  titre en fallback (si le DVD n'est pas trouvé sur DVDFr, ou pour tout ajout sans
  code-barre).
- **Ciné-Roulette** (`/roulette`) : tirage aléatoire d'un DVD, avec rebond possible
  sur la même couleur ou le même genre que le film tiré.
- **Quota DVDFr** : compteur visible sur la page de scan (200 requêtes/semaine),
  avec reset manuel (jusqu'à 5 fois) et avertissement dans les logs sous 20
  requêtes restantes.
- **Logs** : fichier `logs/app.log` avec rotation, format
  `timestamp | niveau | module | message`.

## Installation (développement local)

Prérequis : Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# éditer .env et renseigner les clés API (voir section suivante)

python run.py
```

L'application est accessible sur `http://localhost:5000`. La base SQLite et le
dossier `logs/` sont créés automatiquement au premier lancement.

## Clés API

Trois clés sont nécessaires pour l'enrichissement automatique. L'application reste
utilisable sans elles (ajout manuel toujours disponible), mais chaque intégration
absente est simplement ignorée (avec un `WARNING` dans les logs).

| Variable | Où l'obtenir | Note |
|---|---|---|
| `DVDFR_API_KEY` | [dvdfr.com/api](https://www.dvdfr.com/api) | Inscription requise. Quota 200 req/semaine. |
| `TMDB_API_KEY` | [themoviedb.org](https://www.themoviedb.org/) → paramètres → API | Gratuit, formulaire décrivant l'usage de l'app. |
| `OMDB_API_KEY` | [omdbapi.com](https://www.omdbapi.com/apikey.aspx) | Gratuit, 1000 req/jour. |

Copier `.env.example` vers `.env` et renseigner les valeurs. `.env` n'est jamais
versionné (voir `.gitignore`).

> **Note d'implémentation** : l'API DVDFr (`productlist.php`) n'a pas de
> documentation publique stable ; le format exact des paramètres d'authentification
> et de la réponse peut varier selon les comptes. Le module
> [`cineroulette/services/dvdfr.py`](cineroulette/services/dvdfr.py) parse la
> réponse de façon défensive (plusieurs formes de JSON acceptées) et journalise un
> `WARNING` si un champ attendu n'est pas reconnu — à ajuster si le format constaté
> diffère une fois une vraie clé en main.

## Lancer avec Docker

```bash
cp .env.example .env
# renseigner les clés API dans .env

docker compose up -d --build
```

Le `docker-compose.yml` monte trois volumes persistants (survivent aux rebuilds) :

- `./instance` → base SQLite
- `./cineroulette/static/covers` → jaquettes téléchargées
- `./logs` → fichier de logs

L'application écoute sur le port `5000` (servie par `gunicorn`).

## HTTPS local (nécessaire pour le scan caméra sur mobile)

Les navigateurs n'autorisent l'accès caméra (`getUserMedia`) que sur une origine
sécurisée (HTTPS) ou `localhost`. Pour tester le scan depuis un smartphone sur le
réseau local, le plus simple est [mkcert](https://github.com/FiloSottile/mkcert) :
il crée une autorité de certification locale que tu installes sur tes appareils,
puis génère des certificats reconnus comme valides (pas d'avertissement navigateur).

```bash
brew install mkcert
mkcert -install          # installe l'autorité locale dans le trousseau macOS

cd "chemin/vers/ciné-roulette"
mkcert 192.168.1.167 localhost 127.0.0.1   # remplacer par l'IP actuelle du Mac
# génère 192.168.1.167+2.pem (certificat) et 192.168.1.167+2-key.pem (clé)
```

Puis dans `.env` :

```
SSL_CERT_FILE=/chemin/absolu/vers/192.168.1.167+2.pem
SSL_KEY_FILE=/chemin/absolu/vers/192.168.1.167+2-key.pem
```

`python run.py` sert alors en HTTPS sur `https://192.168.1.167:5000`. Sur Mac, ce
sera déjà "de confiance" (Safari/Chrome). **Sur iPhone**, il faut en plus installer
l'autorité mkcert sur le téléphone :

1. Récupérer le fichier racine : `mkcert -CAROOT` indique le dossier contenant
   `rootCA.pem`. Envoie ce fichier sur le téléphone (AirDrop, mail...).
2. L'ouvrir sur l'iPhone installe un profil de configuration
   (Réglages → Général → VPN et gestion de l'appareil → installer).
3. Puis Réglages → Général → Informations → Réglages de confiance des certificats
   → activer la confiance totale pour le certificat "mkcert...".

Une fois fait, `https://192.168.1.167:5000` s'affiche sans avertissement sur le
téléphone et l'accès caméra fonctionne.

> ⚠️ Le certificat est lié à l'IP indiquée lors de la génération. Si l'IP du Mac
> change (DHCP), il faut régénérer un certificat avec `mkcert <nouvelle-ip> localhost 127.0.0.1`.

`SSL_CERT_FILE`/`SSL_KEY_FILE` ne s'appliquent qu'au serveur de dev (`python
run.py`). Pour `gunicorn`/Docker, utiliser plutôt un reverse proxy TLS devant
l'application (voir section suivante).

## Déploiement homelab (LXC Proxmox)

- Conteneuriser via Docker (ci-dessus) dans un conteneur LXC, ou lancer directement
  `gunicorn` dans un LXC Python.
- Exposer en réseau local, ou à distance via WireGuard.
- **Scan caméra** : comme en local, prévoir un reverse proxy avec certificat
  (mkcert, auto-signé, ou Let's Encrypt via DNS interne) devant l'application pour
  servir en HTTPS.

## Structure du projet

```
cineroulette/
├── config.py              # configuration (clés API, chemins, couleurs valides)
├── models.py               # modèle Dvd + compteur de quota DVDFr
├── routes/
│   ├── dvd.py               # CRUD, scan, recherche manuelle TMDB
│   └── roulette.py          # page roulette + /random
├── services/
│   ├── dvdfr.py, tmdb.py, omdb.py   # intégrations externes
│   ├── quota.py             # suivi local du quota DVDFr
│   └── covers.py            # téléchargement/conversion des jaquettes
├── templates/                # Jinja2
└── static/
    ├── css/style.css
    ├── js/                   # recherche live, scan, roulette, recherche TMDB
    └── covers/                # jaquettes téléchargées (<id>.jpg)
run.py                        # point d'entrée (dev + gunicorn)
Dockerfile / docker-compose.yml
```

## Limitations connues (hors périmètre de cette version)

- Pas d'authentification multi-utilisateurs.
- Pas d'export/import de collection.
- Pas de statistiques de collection.
- Pas de protection CSRF sur les formulaires (acceptable pour un usage
  mono-utilisateur en réseau local ; à ajouter si l'app devait s'ouvrir plus
  largement).

Ces points peuvent être ajoutés dans une itération future si besoin.
