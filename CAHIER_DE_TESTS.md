# Cahier de tests — Ciné-Roulette

Plan de test de référence pour valider le fonctionnement technique et fonctionnel
de l'application, construit à partir du cahier des charges initial et de toutes
les évolutions décidées depuis (remplacement DVDFr → UPCitemdb, anti-doublon,
hashtags, roulette, favicon, couleur verte, scanner Quagga2, etc.).

Ce document est un **plan de test stable** : il décrit les cas de test une fois
pour toutes. Il n'enregistre pas d'historique d'exécution — à chaque
modification de l'application, Claude rejoue les tests pertinents et communique
les résultats (OK / échec / régression) directement dans la conversation.

---

## 1. Conventions

### 1.1 Format d'un cas de test

Chaque cas de test suit cette structure (inspirée ISTQB/IEEE 829, simplifiée) :

| Champ | Signification |
|---|---|
| **ID** | Identifiant unique (`TF-xxx` = test fonctionnel, `TT-xxx` = test technique) |
| **Priorité** | Critique / Haute / Moyenne / Basse |
| **Exécutant** | Qui peut réaliser ce test (voir §1.2) |
| **Préconditions** | État requis avant le test |
| **Étapes** | Actions à réaliser, dans l'ordre |
| **Données de test** | Jeu de données concret à utiliser |
| **Résultat attendu** | Ce qui doit être observé si le test passe |

### 1.2 Qui exécute quoi

- **Claude (auto)** — testable sans intervention humaine : appels HTTP directs
  (`curl`, client de test Flask), lecture de base de données, navigateur
  automatisé (captures d'écran, clics, lecture du DOM).
- **Utilisateur (manuel)** — nécessite un jugement humain ou un matériel que
  Claude ne peut pas simuler : appareil photo réel, avis visuel/esthétique,
  accès à Proxmox/Portainer.
- **Mixte** — Claude peut valider la mécanique/le backend, l'utilisateur valide
  le rendu final ou l'expérience réelle.

### 1.3 Règle d'or : jamais sur les vraies données

Tous les tests **Claude (auto)** qui créent/modifient/suppriment des DVD
s'exécutent sur une base isolée (`DATABASE_URL=sqlite:////tmp/...` pointant vers
un fichier temporaire, ou le client de test Flask en mémoire), **jamais** sur
`instance/cineroulette.db`. Si le serveur de développement de l'utilisateur
tourne déjà (port 5000 occupé), Claude n'y touche pas et lance une instance
scratch sur un autre port avec une base temporaire.

**⚠️ Isoler la base ne suffit pas.** `COVERS_DIR` (`cineroulette/static/covers/`)
n'est **pas** dérivé de `DATABASE_URL` — un test qui télécharge/upload une
jaquette écrit dans le vrai dossier de jaquettes même avec une base temporaire,
et peut donc **écraser un fichier réel** si l'ID généré dans la base de test
coïncide avec un ID existant en production (déjà arrivé une fois : le test a
écrasé `covers/1.jpg`, la vraie jaquette d'un DVD réel, restauré ensuite depuis
TMDB). Avant tout test impliquant une jaquette (TF-106, TF-107, TF-401, TF-402),
**toujours** surcharger explicitement `app.config["COVERS_DIR"]` vers un
répertoire temporaire juste après `create_app()` :

```python
app.config["COVERS_DIR"] = Path("/tmp/cineroulette_test_covers")
app.config["COVERS_DIR"].mkdir(parents=True, exist_ok=True)
```

**Cette règle s'applique à tout code qui télécharge une jaquette, pas
seulement aux routes web** — l'erreur s'est reproduite une deuxième fois lors
du test d'une première version de `scripts/import_csv.py`, qui accédait
directement à `COVERS_DIR`. Ce script a depuis été réécrit pour ne piloter
l'application que via ses routes HTTP (`--base-url`) : il n'a plus aucun accès
direct au disque ou à la base. La règle d'isolement s'applique donc à
l'**instance ciblée par `--base-url`** — toujours la faire pointer vers un
serveur scratch temporaire (base + `COVERS_DIR` isolés), jamais vers le
serveur réel de l'utilisateur.

### 1.4 Jeux de données de référence (EAN réels validés)

| EAN | Titre UPCitemdb brut | Après nettoyage | Résultat TMDB attendu |
|---|---|---|---|
| `0462041620263` | "Pre-Owned The Matrix (Dvd) (Good)" | "The Matrix" | Matrix (1999), Action/Science-Fiction, IMDb ~8.7 |
| `3333297300612` | "La 5ème Vague [dvd + Copie Di Dvd Value Guaranteed From Ebay's Biggest Seller" | "La 5ème Vague" | La 5ème Vague / The 5th Wave (2016), IMDb ~5.2 |
| `7321950131761` | "Care With Un Vampire Dvd Blister Pack" | (mistraduit, non nettoyable) | Aucun résultat TMDB automatique — sert au test de correction manuelle |

### 1.5 Portée d'exécution après une modification

- **Modification ciblée** (ex: un template, une route) → rejouer le sous-groupe
  concerné + le **smoke test** (§2).
- **Modification transverse** (modèle de données, config, service partagé) →
  rejouer la suite complète pertinente.
- Dans tous les cas, Claude indique explicitement quels tests ont été rejoués,
  lesquels ont été jugés non concernés, et alerte immédiatement en cas de
  régression avant de proposer un correctif.

---

## 2. Smoke test (passage rapide après toute modification)

| ID | Test | Résultat attendu |
|---|---|---|
| ST-01 | `GET /dvd` répond 200 | Page collection s'affiche |
| ST-02 | `GET /dvd/new` puis créer un DVD manuel (TF-101) | DVD créé, visible dans la collection |
| ST-03 | `GET /roulette` répond 200 et un film s'affiche sans clic (TF-501) | Film affiché immédiatement |
| ST-04 | `GET /dvd/scan` répond 200 | Page de scan s'affiche, pas d'erreur JS bloquante |
| ST-05 | Filtrer par couleur et par hashtag (TF-201, TF-203) | Résultats corrects |
| ST-06 | Supprimer le DVD créé en ST-02 | Retour à l'état initial, pas d'erreur |
| ST-07 | `logs/app.log` s'est mis à jour pendant les tests ci-dessus | Nouvelles lignes au format `timestamp \| niveau \| module \| message` |

Si un seul de ces 7 points échoue, considérer la modification comme **non
validée** et creuser avant d'aller plus loin.

---

## 3. Modèle de données & contraintes (technique)

**TT-001 — Contrainte CHECK sur `couleur`**
- Priorité : Critique · Exécutant : Claude (auto)
- Préconditions : base de test isolée créée via `create_app()`
- Étapes :
  1. Tenter d'insérer un `Dvd` avec `couleur="violet"` directement via SQLAlchemy (contournant la validation applicative)
  2. Observer l'exception
- Données de test : `Dvd(titre_fr="Invalide", couleur="violet")`
- Résultat attendu : `sqlalchemy.exc.IntegrityError` levée, aucune ligne insérée. Les 4 valeurs autorisées sont exactement `rouge`, `vert`, `dorée`, `argent`.

**TT-002 — Contrainte UNIQUE sur `ean`**
- Priorité : Haute · Exécutant : Claude (auto)
- Étapes : insérer deux `Dvd` avec le même `ean` non nul directement en base
- Résultat attendu : `IntegrityError` sur la deuxième insertion (indépendamment de la vérification applicative testée en TF-301)

**TT-003 — Colonne `tmdb_id` nullable, pas de contrainte UNIQUE en base**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Étapes : insérer deux `Dvd` avec le même `tmdb_id` mais des `ean` différents
- Résultat attendu : les deux insertions réussissent (deux éditions physiques du même film sont autorisées ; seule la couche applicative bloque le cas sans EAN, cf. TF-303)

**TT-004 — `date_ajout` et `updated_at` auto-renseignés**
- Priorité : Basse · Exécutant : Claude (auto)
- Résultat attendu : `date_ajout` non nul à la création, `QuotaCounter.updated_at` change après un `increment()`

---

## 4. CRUD DVD (fonctionnel)

**TF-101 — Ajout manuel valide**
- Priorité : Critique · Exécutant : Claude (auto)
- Étapes : `POST /dvd/new` avec titre + couleur valide
- Données de test : `titre_fr=Oblivion, couleur=argent, annee=2013, theme=Action, Science-Fiction`
- Résultat attendu : 302 vers `/dvd/<id>`, DVD visible en base, log `INFO ... DVD ajouté`

**TF-102 — Ajout refusé si titre manquant**
- Priorité : Haute · Exécutant : Claude (auto)
- Étapes : `POST /dvd/new` sans `titre_fr`
- Résultat attendu : HTTP 400, message flash "Le titre français est requis.", aucun DVD créé

**TF-103 — Ajout refusé si couleur invalide ou absente**
- Priorité : Haute · Exécutant : Claude (auto)
- Données de test : `couleur=violet`
- Résultat attendu : HTTP 400, message "Merci de choisir une couleur valide.", aucun DVD créé

**TF-104 — Modification d'un DVD**
- Priorité : Haute · Exécutant : Claude (auto)
- Étapes : créer un DVD, puis `POST /dvd/<id>/edit` avec de nouvelles valeurs
- Résultat attendu : champs mis à jour en base, redirection vers la fiche, log `INFO ... DVD modifié`

**TF-105 — Suppression d'un DVD**
- Priorité : Haute · Exécutant : Mixte (Claude peut poster la requête ; la confirmation JS `onsubmit` est visuelle donc à valider une fois par l'utilisateur)
- Étapes : `POST /dvd/<id>/delete`
- Résultat attendu : DVD supprimé, jaquette associée supprimée du disque si présente, redirection vers `/dvd`, log `INFO ... DVD supprimé`

**TF-106 — Téléchargement de jaquette depuis une URL**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Étapes : `POST /dvd/new` avec `jaquette_url` pointant vers une image valide
- Résultat attendu : fichier `covers/<id>.jpg` créé, `jaquette_path` renseigné

**TF-107 — Upload de jaquette invalide (fichier non-image)**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Étapes : `POST /dvd/new` avec `jaquette_file` = un fichier texte/CSS renommé
- Résultat attendu : le DVD est quand même créé (le champ n'est pas bloquant), `jaquette_path` reste vide, log `ERROR ... Fichier jaquette illisible` — pas de crash 500

**TF-108 — Pagination de la collection**
- Priorité : Basse · Exécutant : Claude (auto)
- Préconditions : plus de 24 DVD en base (`PER_PAGE = 24`)
- Résultat attendu : `pagination.pages > 1`, liens "Précédent"/"Suivant" corrects et conservant `q`/`couleur`/`theme`

---

## 5. Recherche & filtres (fonctionnel)

**TF-201 — Recherche partielle insensible à la casse**
- Priorité : Haute · Exécutant : Claude (auto)
- Données de test : DVD "Matrix" en base, recherche `q=matr` puis `q=MATR`
- Résultat attendu : les deux requêtes retournent le film ; recherche sur `titre_fr` **et** `titre_en`

**TF-202 — Recherche sans résultat**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Données de test : `q=zzzzz`
- Résultat attendu : message "Aucun DVD ne correspond à « zzzzz »." (pas de liste vide silencieuse)

**TF-203 — Filtre par couleur**
- Priorité : Haute · Exécutant : Claude (auto)
- Résultat attendu : `GET /dvd?couleur=vert` ne retourne que les DVD de cette couleur

**TF-204 — Filtre par hashtag (thème unique dans un champ multi-valeurs)**
- Priorité : Haute · Exécutant : Claude (auto)
- Données de test : DVD A `theme="Action, Science-Fiction, Aventure, Mystère"`, DVD B `theme="Action, Science-Fiction"`
- Étapes : `GET /dvd?theme=Action`, puis `GET /dvd?theme=Mystère`
- Résultat attendu : le 1er retourne A et B ; le 2e ne retourne que A

**TF-205 — Comptage des hashtags affichés**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Résultat attendu : `_known_themes()` retourne chaque hashtag avec le bon nombre d'occurrences, trié alphabétiquement (ex : `Action (2)`, `Mystère (1)`)

**TF-206 — Combinaison recherche + couleur + hashtag**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Résultat attendu : les 3 filtres s'appliquent en ET logique

**TF-207 — Recherche live sans rechargement de page (JS)**
- Priorité : Moyenne · Exécutant : Mixte (Claude vérifie via navigateur automatisé que le `fetch` remplace `#dvd-grid` sans navigation complète ; confort de frappe à confirmer par l'utilisateur)
- Résultat attendu : taper dans la barre de recherche déclenche un `fetch` (debounce ~300ms) vers `/dvd?...` avec l'en-tête `X-Requested-With: fetch`, le contenu de `#dvd-grid` se met à jour, l'URL change via `history.replaceState`

---

## 6. Anti-doublon (fonctionnel + technique)

**TF-301 — Refus d'ajout manuel avec un EAN déjà utilisé**
- Priorité : Critique · Exécutant : Claude (auto)
- Étapes : créer un DVD avec `ean=1234567890123`, puis retenter un ajout avec le même EAN
- Résultat attendu : HTTP 400, message "Ce film est déjà dans la collection : « ... », ajouté le ...", un seul DVD en base

**TF-302 — Détection de doublon dès le scan (avant tout appel API)**
- Priorité : Critique · Exécutant : Claude (auto)
- Étapes : créer un DVD avec un EAN donné, puis `POST /dvd/scan` avec ce même EAN
- Résultat attendu : écran "Déjà dans la collection" avec jaquette/titre/lien vers la fiche existante ; **aucun appel** UPCitemdb (quota inchangé, vérifiable via `quota.get_status`) ; le lecteur caméra reste actif juste en dessous pour enchaîner sur le disque suivant

**TF-303 — Refus d'ajout manuel via TMDB si même `tmdb_id` sans EAN**
- Priorité : Haute · Exécutant : Claude (auto)
- Étapes : ajouter un DVD via `tmdb_id=628` sans EAN, puis retenter un ajout avec le même `tmdb_id`, toujours sans EAN
- Résultat attendu : 2ᵉ tentative refusée (400), message "Ce film est déjà dans la collection"

**TF-304 — Même `tmdb_id` mais EAN différent = autorisé (2ᵉ édition physique)**
- Priorité : Haute · Exécutant : Claude (auto)
- Résultat attendu : les deux DVD sont créés sans erreur (deux exemplaires physiques légitimes du même film)

**TF-305 — Édition : conserver son propre EAN sans se bloquer soi-même**
- Priorité : Haute · Exécutant : Claude (auto)
- Étapes : créer un DVD avec un EAN, puis `POST /dvd/<id>/edit` en renvoyant le même EAN
- Résultat attendu : succès (302), pas de faux positif de doublon

**TF-306 — Édition : refus de voler l'EAN d'un autre DVD**
- Priorité : Haute · Exécutant : Claude (auto)
- Étapes : créer DVD A (ean=1111) et DVD B (ean=2222), puis éditer B avec `ean=1111`
- Résultat attendu : HTTP 400, l'EAN de A n'est pas modifié, message d'erreur explicite

**TF-307 — Ajout 100% manuel sans EAN ni tmdb_id : pas de blocage**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Résultat attendu : deux DVD avec le même titre mais sans EAN/tmdb_id peuvent coexister (aucun identifiant fiable disponible — comportement inchangé, assumé)

---

## 7. Enrichissement scan : UPCitemdb → TMDB → OMDb (fonctionnel)

**TF-401 — Pipeline complet réussi (cas nominal)**
- Priorité : Critique · Exécutant : Claude (auto, avec clés API réelles configurées)
- Données de test : EAN `0462041620263`
- Résultat attendu : `source=upcitemdb`, `titre_fr="Matrix"` (titre TMDB, pas le titre brut revendeur), `annee=1999`, `theme` contient "Action" et "Science-Fiction", `note_imdb` renseignée, `jaquette_url` non vide, aucun message d'avertissement

**TF-402 — Titre revendeur bruité mais nettoyable**
- Priorité : Haute · Exécutant : Claude (auto)
- Données de test : EAN `3333297300612`
- Résultat attendu : `clean_title_for_search()` retourne "La 5ème Vague" (troncature au premier marqueur d'annonce type `[`), TMDB trouve "The 5th Wave" (2016), aucun avertissement affiché

**TF-403 — Titre mal traduit, non récupérable automatiquement**
- Priorité : Haute · Exécutant : Claude (auto)
- Données de test : EAN `7321950131761`
- Résultat attendu : flash "Aucun résultat TMDB pour « ... »", le formulaire de résultat s'affiche quand même avec le titre brut en `titre_fr`, et le widget de recherche manuelle TMDB est pré-rempli et lance une recherche automatiquement

**TF-404 — Correction manuelle après échec d'enrichissement**
- Priorité : Haute · Exécutant : Mixte (Claude valide le remplissage des champs via clic automatisé ; confort réel à l'usage laissé à l'utilisateur)
- Étapes : sur l'écran TF-403, remplacer la recherche par "Entretien avec un vampire", cliquer sur la vignette proposée
- Résultat attendu : `titre_fr`, `titre_en`, `resume`, `theme`, `annee`, `note_imdb`, `jaquette_url` et le champ caché `tmdb_id` se remplissent avec les données du film sélectionné

**TF-405 — EAN introuvable sur UPCitemdb**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Données de test : EAN inventé improbable, ex `0000000000000`
- Résultat attendu : flash "EAN non trouvé via UPCitemdb...", formulaire vide affiché, pas d'exception

**TF-406 — Clés API absentes**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Préconditions : `TMDB_API_KEY`/`OMDB_API_KEY` vides
- Résultat attendu : chaque intégration absente logue un `WARNING` explicite et est simplement ignorée, sans crash

---

## 8. Quota UPCitemdb (technique)

**TT-101 — Décrément du compteur à chaque appel**
- Priorité : Haute · Exécutant : Claude (auto)
- Résultat attendu : `quota.increment("upcitemdb")` incrémente `count`, log `INFO ... Quota upcitemdb décrémenté : x/100`

**TT-102 — Avertissement sous le seuil**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Préconditions : compteur positionné à 91/100 (seuil = 10 restantes)
- Résultat attendu : le prochain appel loggue un `WARNING` "Quota ... bientôt épuisé"

**TT-103 — Renouvellement automatique après 24h**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Étapes : positionner `period_start` à plus de 24h dans le passé, appeler `get_status()`
- Résultat attendu : compteur remis à 0, nouveau `period_start`, log `INFO ... nouvelle période`

**TT-104 — Appel UPCitemdb bloqué si quota épuisé**
- Priorité : Haute · Exécutant : Claude (auto)
- Préconditions : `count = 100`
- Résultat attendu : `upcitemdb.lookup_by_ean()` retourne `None` sans appel HTTP réel, log `WARNING ... quota épuisé ... bascule fallback manuel`

---

## 9. Ajout manuel via recherche TMDB & import en masse (fonctionnel)

**TF-501 — Recherche et sélection d'un film**
- Priorité : Haute · Exécutant : Claude (auto)
- Étapes : `GET /dvd/tmdb_search?q=Oblivion` puis `GET /dvd/tmdb_pick?movie_id=<id>`
- Résultat attendu : liste de candidats avec `titre_fr`, `titre_en`, `annee`, `poster_url` ; la sélection retourne un objet complet incluant `tmdb_id` et `note_imdb`

**TF-502 — Widget de recherche présent uniquement en mode création**
- Priorité : Basse · Exécutant : Claude (auto)
- Résultat attendu : le bloc `#tmdb-query` n'apparaît pas sur `/dvd/<id>/edit` (pas de champ `tmdb_id` modifiable en édition)

**TF-503 — `scripts/import_csv.py` : import réel depuis un CSV**
- Priorité : Haute · Exécutant : Claude (auto, **contre une instance scratch dédiée** — `--base-url` pointé sur un serveur temporaire avec base et `COVERS_DIR` isolés, jamais sur le serveur réel de l'utilisateur ; voir §1.3)
- Préconditions : le script ne fait **aucun accès direct** à la base/au disque — il pilote l'application uniquement via `/dvd/tmdb_search`, `/dvd/tmdb_pick`, `/dvd/new`, exactement comme un navigateur. Fonctionne donc identiquement en local ou contre le conteneur Docker réel, pourvu que `--base-url` soit atteignable.
- Données de test :
  ```
  titre,couleur
  Matrix,rouge
  Le Roi Lion,or
  Matrix,rouge
  Inception,violet
  zzzzxxxxyyyyfilmquinexistepas,argent
  ```
- Résultat attendu : ligne 1 → `importé` (Matrix, couleur=rouge, tmdb_id renseigné, jaquette téléchargée côté serveur) ; ligne 2 → `importé` avec couleur normalisée `or` → `dorée` ; ligne 3 → `doublon` (message repris du flash `error` du serveur : « Ce film est déjà dans la collection... ») ; ligne 4 → `erreur` (couleur "violet" non reconnue, aucun appel réseau émis) ; ligne 5 → `introuvable` (aucun résultat TMDB) ; un fichier `<nom>_resultat_<date>.csv` est généré avec le détail par ligne

**TF-504 — `scripts/import_csv.py --dry-run`**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Résultat attendu : mêmes correspondances trouvées et affichées (recherche + détail TMDB réellement appelés), mais **aucun `POST /dvd/new` n'est envoyé** ; les doublons au sein du même lot ne sont pas détectés en dry-run (la détection dépend d'un enregistrement déjà créé côté serveur, qui n'a jamais lieu ici) — comportement attendu, à ne pas confondre avec un bug

**TT-701 — `scripts/import_csv.py` : application injoignable**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Étapes : lancer le script avec `--base-url` pointant vers un port fermé
- Résultat attendu : message clair "Impossible de joindre l'application sur ..." et sortie immédiate (code 1), sans tenter d'appeler TMDB ligne par ligne

---

## 10. Roulette (fonctionnel)

**TF-601 — Tirage immédiat au chargement de la page**
- Priorité : Critique · Exécutant : Claude (auto, navigateur automatisé)
- Étapes : charger `/roulette` avec au moins un DVD en base
- Résultat attendu : un film s'affiche sans clic sur "Film au hasard"

**TF-602 — "Film au hasard" exclut le film courant**
- Priorité : Haute · Exécutant : Claude (auto)
- Résultat attendu : `GET /random?exclude=<id>` ne retourne jamais ce même `id` (sauf s'il est le seul DVD en base)

**TF-603 — "Même couleur" filtre correctement**
- Priorité : Haute · Exécutant : Claude (auto)
- Résultat attendu : `GET /random?couleur=X&exclude=id` ne retourne que des DVD de couleur X

**TF-604 — "Même genre" par hashtag individuel**
- Priorité : Critique · Exécutant : Claude (auto, navigateur automatisé)
- Données de test : Oblivion (`Action, Science-Fiction, Aventure, Mystère`), Matrix (`Action, Science-Fiction`)
- Étapes : tirer Oblivion, cliquer sur le hashtag `#Action`
- Résultat attendu : bascule vers un autre film partageant ce tag précis (Matrix) ; les hashtags affichés se mettent à jour avec ceux du nouveau film tiré

**TF-605 — Cas limite : un seul DVD dans la catégorie**
- Priorité : Haute · Exécutant : Claude (auto)
- Résultat attendu : message "Un seul DVD dans cette catégorie pour l'instant." ; le film actuellement affiché reste visible (pas de re-tirage silencieux du même film)

**TF-606 — Cas limite : catégorie totalement vide**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Résultat attendu : message "Aucun DVD dans cette catégorie pour l'instant."

**TF-607 — Collection vide**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Résultat attendu : le tirage automatique au chargement affiche le message "Aucun DVD..." sans erreur JS

---

## 10bis. Disponibilité streaming (TMDB watch/providers — fonctionnel + technique)

Contexte : pour chaque film lié à TMDB, on affiche les plateformes d'abonnement
(**flatrate**) où il est disponible **en France** (`STREAMING_REGION = "FR"`),
via l'endpoint TMDB `/movie/{id}/watch/providers` (données JustWatch). Ni
location, ni achat, ni lien « Regarder ». Endpoint applicatif :
`GET /streaming/<tmdb_id>` → `{"providers": [{"name", "logo_url"}, ...]}`.
Cache local en base (`streaming_cache`), rafraîchi après `STREAMING_CACHE_HOURS`
(48 h par défaut).

**TF-610 — Affichage des plateformes sur la fiche détail**
- Priorité : Critique · Exécutant : Claude (auto, navigateur automatisé)
- Données de test : un DVD avec `tmdb_id` disponible en flatrate FR (ex. Fight Club, tmdb_id 550)
- Résultat attendu : sous le résumé, label « 📺 En streaming (abonnement) » suivi d'une rangée de logos de plateformes

**TF-611 — Affichage des plateformes dans la carte roulette**
- Priorité : Haute · Exécutant : Claude (auto, navigateur automatisé)
- Résultat attendu : même bloc streaming dans la carte tirée ; les logos sont de petits carrés uniformes (40 px), non étirés par la règle de jaquette `.roulette-card img`

**TF-612 — Film indisponible en streaming FR**
- Priorité : Haute · Exécutant : Claude (auto)
- Résultat attendu : message clair « 📺 Pas disponible en streaming (abonnement) » (pas de rangée de logos vide)

**TF-613 — Film sans `tmdb_id`**
- Priorité : Haute · Exécutant : Claude (auto, navigateur automatisé)
- Résultat attendu : aucune section streaming affichée (état inconnu, à distinguer d'une indisponibilité), ni sur la fiche ni dans la roulette

**TT-210 — Filtrage région + catégorie**
- Priorité : Critique · Exécutant : Claude (auto)
- Résultat attendu : seule la clé `FR` de `results` est lue, et seule la catégorie `flatrate` est retenue (les entrées `rent`/`buy`/`ads`/`free` et les autres pays sont ignorés) ; tri par `display_priority` croissant

**TT-210bis — Variantes/revendeurs écartés**
- Priorité : Haute · Exécutant : Claude (auto)
- Résultat attendu : les entrées faisant doublon avec la plateforme mère sont retirées (marqueurs `_VARIANT_MARKERS` : « with ads », « amazon channel », « apple tv channel », « channel ») ; ex. « Netflix Standard with Ads » et « HBO Max Amazon Channel » n'apparaissent pas ; dédoublonnage par nom

**TT-211 — Cache 48 h**
- Priorité : Haute · Exécutant : Claude (auto)
- Résultat attendu : un 1ᵉʳ appel écrit une ligne `streaming_cache` ; un 2ᵉ appel dans les 48 h ne redéclenche pas d'appel TMDB (valeur servie depuis le cache) ; l'état négatif (liste vide) est mis en cache lui aussi

**TT-212 — Robustesse en cas d'échec TMDB**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Résultat attendu : sur échec réseau/API, on sert le cache périmé s'il existe, sinon une liste vide ; jamais d'erreur 500

**TT-213 — Isolation lors des tests (règle d'or)**
- Priorité : Critique · Exécutant : Claude (auto)
- Rappel : `streaming_cache` est en base — tout test écrivant dedans doit isoler `SQLALCHEMY_DATABASE_URI` **avant** `create_all()` (via un `config_class` passé à `create_app`, pas une surcharge post-création qui ne rebinde pas le moteur) **et** `COVERS_DIR`

---

## 11. Scan caméra — Quagga2 (technique + manuel)

**TT-201 — Chargement de la librairie sans erreur JS**
- Priorité : Haute · Exécutant : Claude (auto, navigateur automatisé)
- Résultat attendu : `window.Quagga` défini, `Quagga.init()` appelé, pas d'exception non gérée dans la console

**TT-202 — Gestion propre d'un refus d'accès caméra**
- Priorité : Haute · Exécutant : Claude (auto)
- Résultat attendu : message "Accès caméra refusé." affiché (pas de page cassée) quand `NotAllowedError` est renvoyé

**TT-203 — Gestion propre d'une absence de caméra**
- Priorité : Moyenne · Exécutant : Claude (auto, si simulable) sinon Utilisateur
- Résultat attendu : message "Aucune caméra détectée sur cet appareil."

**TF-608 — Lecture réelle d'un code-barre EAN-13 (fiabilité)**
- Priorité : Critique · Exécutant : **Utilisateur (manuel, obligatoire)**
- Préconditions : app servie en HTTPS (mkcert), accès caméra autorisé sur le téléphone
- Étapes : scanner successivement 5 DVD physiques différents avec un bon éclairage
- Données de test : jaquettes réelles de la collection
- Résultat attendu : taux de lecture nettement supérieur à l'ancien ~10% (objectif indicatif : au moins 7-8 lectures réussies sur 10 essais) ; un code n'est validé qu'après confirmation (3 lectures identiques consécutives, cf. `scan.js`)
- Note : Claude ne peut pas exécuter ce test (pas de caméra physique) — résultat à communiquer après usage réel.

**TF-609 — Cadre de détection visuel pendant le scan**
- Priorité : Basse · Exécutant : Utilisateur (manuel)
- Résultat attendu : un cadre coloré apparaît en direct autour du code-barre repéré par la caméra

---

## 12. Sécurité & robustesse (technique)

**TT-301 — Injection SQL sur la recherche**
- Priorité : Haute · Exécutant : Claude (auto)
- Données de test : `q=' OR '1'='1`
- Résultat attendu : traité comme une chaîne littérale (requêtes paramétrées SQLAlchemy), aucune fuite de données, pas d'erreur 500

**TT-302 — XSS sur les champs texte (titre, résumé, thème)**
- Priorité : Haute · Exécutant : Claude (auto)
- Données de test : `titre_fr=<script>alert(1)</script>`
- Résultat attendu : échappement Jinja2 automatique (`{{ }}`), le tag s'affiche en texte brut dans le HTML rendu, jamais exécuté

**TT-303 — Upload de fichier non-image renommé en `.jpg`**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Résultat attendu : Pillow lève `UnidentifiedImageError`, capturée et loggée en `ERROR`, pas de fichier corrompu écrit sur disque

**TT-304 — Path traversal via nom de fichier de couverture**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Résultat attendu : les fichiers sont toujours nommés `<id>.jpg` côté serveur (jamais le nom fourni par l'utilisateur), donc pas de vecteur de traversée de répertoire

**TT-305 — Accès à une fiche DVD inexistante**
- Priorité : Basse · Exécutant : Claude (auto)
- Étapes : `GET /dvd/999999`
- Résultat attendu : HTTP 404 (`get_or_404`)

**TT-306 — Anti-cache des fichiers statiques (`?v=<mtime>`)**
- Priorité : Haute · Exécutant : Claude (auto)
- Contexte : `dated_url_for` (dans `__init__.py`) suffixe chaque asset statique de sa date de modification, pour éviter que navigateurs/proxys servent un CSS/JS périmé après mise à jour
- Étapes / résultat attendu :
  - le HTML servi porte `css/style.css?v=<entier>` (idem JS, favicons) ;
  - modifier un fichier statique change son suffixe `?v=` ;
  - un asset introuvable (ex. jaquette supprimée) est rendu **sans** suffixe (repli `OSError`) et **ne casse pas** la page (pas de 500)

---

## 13. Journalisation (technique)

**TT-401 — Format des lignes de log**
- Priorité : Haute · Exécutant : Claude (auto)
- Résultat attendu : chaque ligne respecte `YYYY-MM-DD HH:MM:SS | NIVEAU | module | message`

**TT-402 — Rotation des logs**
- Priorité : Basse · Exécutant : Claude (auto, si testable sans attendre 5×5 Mo réels — sinon inspection de la config uniquement)
- Résultat attendu : `RotatingFileHandler` configuré avec `maxBytes=5*1024*1024`, `backupCount=5`

**TT-403 — Niveaux de log cohérents avec le cahier des charges**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Résultat attendu : ajout/modif/suppression DVD → `INFO` ; fallback TMDB/OMDb introuvable → `WARNING` ; échec d'appel API externe → `ERROR`

---

## 14. HTTPS local (technique, semi-manuel)

**TT-501 — Serveur refuse le HTTP simple quand un certificat est configuré**
- Priorité : Moyenne · Exécutant : Claude (auto)
- Préconditions : `SSL_CERT_FILE`/`SSL_KEY_FILE` renseignés dans `.env`
- Résultat attendu : `python run.py` sert uniquement en HTTPS ; une requête HTTP simple sur le même port échoue

**TT-502 — Chargement de `.env` avant lecture de `Config`**
- Priorité : Critique · Exécutant : Claude (auto)
- Résultat attendu : `app.config["SSL_CERT_FILE"]` (et les clés API) reflètent bien le contenu de `.env` — régression déjà rencontrée une fois, à surveiller à chaque modification de `cineroulette/__init__.py`

**TF-701 — Accès mobile en HTTPS sans avertissement**
- Priorité : Moyenne · Exécutant : Utilisateur (manuel)
- Résultat attendu : après installation du profil mkcert sur le téléphone, `https://<ip>:5000` s'affiche sans avertissement de sécurité

---

## 15. Déploiement Docker / Portainer (manuel)

**TT-601 — Build de l'image Docker sans erreur**
- Priorité : Haute · Exécutant : Claude (auto, en local via `docker build` si Docker est disponible sur la machine ; sinon inspection statique du Dockerfile)
- Résultat attendu : `docker build .` se termine sans erreur, `gunicorn` démarre dans le conteneur

**TF-801 — Déploiement complet via Portainer (Proxmox)**
- Priorité : Haute · Exécutant : **Utilisateur (manuel, obligatoire)**
- Résultat attendu : stack Portainer déployé depuis le repo GitHub, application accessible sur `http://<ip-proxmox>:5000`, variables d'environnement prises en compte, volumes persistants après redéploiement

---

## 16. Interface / Design (majoritairement manuel)

**TF-901 — Favicon et icône de titre**
- Priorité : Basse · Exécutant : Mixte (Claude vérifie la présence des balises `<link rel="icon">` et l'absence d'erreur 404 sur les fichiers ; rendu visuel confirmé par l'utilisateur)
- Résultat attendu : dé bleu visible dans l'onglet du navigateur et dans le logo du header, lisible même en petite taille

**TF-902 — Responsive mobile**
- Priorité : Moyenne · Exécutant : Utilisateur (manuel)
- Résultat attendu : collection, fiche détail, formulaire et roulette restent utilisables sur un écran de smartphone

**TF-903 — Thème clair/sombre système**
- Priorité : Basse · Exécutant : Utilisateur (manuel)
- Résultat attendu : les couleurs restent lisibles dans les deux modes (`prefers-color-scheme`)

---

## 17. Traçabilité avec le cahier des charges initial

| Section du cahier des charges | Couverture dans ce plan |
|---|---|
| §3 Modèle de données | TT-001 à TT-004 |
| §4 Intégration DVDFr → **UPCitemdb** (évolution) | TF-401 à TF-406, TT-101 à TT-104 |
| §5 CRUD | TF-101 à TF-108 |
| §6 Recherche par nom partiel | TF-201, TF-202, TF-207 |
| §7 Ciné-Roulette | TF-601 à TF-609 |
| §8 Interface / Frontend | TF-207, TF-901 à TF-903, TF-608 |
| §9 Journalisation | TT-401 à TT-403 |
| §10 Déploiement | TT-601, TF-801, TF-701 |
| *Hors périmètre initial, ajouté depuis* : anti-doublon | TF-301 à TF-307 |
| *Hors périmètre initial, ajouté depuis* : hashtags | TF-203 à TF-206, TF-604 |
| *Hors périmètre initial, ajouté depuis* : sécurité | TT-301 à TT-305 |

---

## 18. Historique des changements majeurs couverts par ce plan

- Remplacement de DVDFr par UPCitemdb (quota, nettoyage de titre, correction manuelle)
- Anti-doublon EAN + `tmdb_id`
- Thèmes en hashtags indépendants (affichage, filtre, compteur, roulette)
- Roulette : tirage immédiat + rebond par genre individuel
- Favicon + icône de marque
- Couleur "bleu" renommée en "vert" (migration de données incluse)
- Scanner caméra : migration html5-qrcode → Quagga2
- Script d'import en masse depuis un CSV (`scripts/import_csv.py`)

*Ce document doit être mis à jour (nouveaux cas de test) à chaque fois qu'une
fonctionnalité notable est ajoutée ou modifiée — pas seulement rejoué à
l'identique.*
