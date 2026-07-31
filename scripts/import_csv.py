#!/usr/bin/env python3
"""Import en masse de DVD depuis un CSV, via l'API HTTP de l'application.

Ce script ne touche ni la base de données ni le système de fichiers
directement : il pilote l'application exactement comme le ferait un
navigateur, via ses routes existantes (/dvd/tmdb_search, /dvd/tmdb_pick,
/dvd/new). Il fonctionne donc aussi bien contre une instance locale
(`python run.py`) que contre l'application déployée dans son conteneur
Docker (Portainer) — pas besoin d'accès direct au conteneur.

Pour chaque ligne, recherche le film sur TMDB (par titre), récupère titre
anglais/résumé/genres/année/jaquette/note IMDb, puis soumet le formulaire
d'ajout — la détection de doublon, le téléchargement de la jaquette et la
validation sont gérés côté serveur, exactement comme un ajout manuel.

Si la recherche renvoie plusieurs films portant exactement le même titre
(même orthographe, ex : un original et son remake), la ligne n'est pas
importée automatiquement : statut "plusieurs possibilités", à traiter à la
main via /dvd/new. Ce cas est détecté aussi bien en dry-run qu'en import réel.

Format du CSV attendu (avec en-tête, colonnes "titre" et "couleur", séparées
par des points-virgules) :

    titre;couleur
    Matrix;rouge
    Le Roi Lion;or
    Oblivion;argent

Couleurs acceptées (insensible à la casse) : rouge, vert, dorée (ou "or",
"doré"), argent.

Usage :
    python scripts/import_csv.py films.csv --base-url http://localhost:5000
    python scripts/import_csv.py films.csv --base-url https://cineroulette.home --dry-run
    python scripts/import_csv.py films.csv --base-url https://192.168.1.52:5000 --insecure
"""
import argparse
import csv
import html
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import requests

COULEUR_SYNONYMES = {
    "rouge": "rouge",
    "red": "rouge",
    "vert": "vert",
    "green": "vert",
    "dorée": "dorée",
    "doree": "dorée",
    "doré": "dorée",
    "dore": "dorée",
    "or": "dorée",
    "gold": "dorée",
    "argent": "argent",
    "silver": "argent",
}

FLASH_ERROR_RE = re.compile(r'flash-error">([^<]*)</li>')


def normalize_couleur(value):
    return COULEUR_SYNONYMES.get(value.strip().lower())


def normalize_title(value):
    """Normalise un titre pour comparaison (accents, casse, espaces) afin de
    détecter des candidats de recherche partageant la même orthographe."""
    if not value:
        return ""
    stripped = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped).strip().lower()


def extract_flash_errors(page_html):
    return [html.unescape(m.strip()) for m in FLASH_ERROR_RE.findall(page_html)]


def process_row(session, base_url, timeout, row_num, titre_brut, couleur_brute, dry_run):
    result = {"ligne": row_num, "titre_saisi": titre_brut, "couleur_saisie": couleur_brute}

    if not titre_brut.strip():
        result["statut"] = "erreur"
        result["detail"] = "Titre vide"
        return result

    couleur = normalize_couleur(couleur_brute)
    if not couleur:
        result["statut"] = "erreur"
        result["detail"] = f"Couleur non reconnue : « {couleur_brute} »"
        return result

    try:
        r = session.get(f"{base_url}/dvd/tmdb_search", params={"q": titre_brut}, timeout=timeout)
        r.raise_for_status()
        candidates = r.json()
    except (requests.RequestException, ValueError) as exc:
        result["statut"] = "erreur"
        result["detail"] = f"Échec recherche TMDB : {exc}"
        return result

    if not candidates:
        result["statut"] = "introuvable"
        result["detail"] = "Aucun résultat TMDB pour ce titre"
        return result

    top_title = normalize_title(candidates[0].get("titre_fr"))
    same_spelling = [c for c in candidates if normalize_title(c.get("titre_fr")) == top_title]
    if len(same_spelling) > 1:
        options = ", ".join(f"« {c.get('titre_fr')} » ({c.get('annee') or '?'})" for c in same_spelling)
        result["statut"] = "plusieurs possibilités"
        result["detail"] = f"{len(same_spelling)} films trouvés avec le même titre, à ajouter à la main : {options}"
        return result

    try:
        r = session.get(
            f"{base_url}/dvd/tmdb_pick", params={"movie_id": candidates[0]["id"]}, timeout=timeout
        )
        r.raise_for_status()
        detail = r.json()
    except (requests.RequestException, ValueError) as exc:
        result["statut"] = "erreur"
        result["detail"] = f"Échec récupération détail TMDB : {exc}"
        return result

    if "error" in detail:
        result["statut"] = "introuvable"
        result["detail"] = detail["error"]
        return result

    if dry_run:
        result["statut"] = "simulé"
        result["detail"] = (
            f"Trouvé et unique : « {detail.get('titre_fr')} » ({detail.get('annee') or '?'}) — "
            "prêt à être importé (rien envoyé, dry-run)"
        )
        return result

    payload = {
        "titre_fr": detail.get("titre_fr") or titre_brut.strip(),
        "titre_en": detail.get("titre_en") or "",
        "resume": detail.get("resume") or "",
        "theme": detail.get("theme") or "",
        "annee": detail.get("annee") or "",
        "note_imdb": detail.get("note_imdb") or "",
        "couleur": couleur,
        "tmdb_id": detail.get("tmdb_id") or "",
        "jaquette_url": detail.get("jaquette_url") or "",
    }

    try:
        r = session.post(f"{base_url}/dvd/new", data=payload, timeout=timeout, allow_redirects=False)
    except requests.RequestException as exc:
        result["statut"] = "erreur"
        result["detail"] = f"Échec de l'envoi : {exc}"
        return result

    if r.status_code in (301, 302):
        result["statut"] = "importé"
        result["detail"] = f"« {payload['titre_fr']} » ajouté ({r.headers.get('Location', '')})"
        return result

    errors = extract_flash_errors(r.text)
    message = " / ".join(errors) if errors else f"HTTP {r.status_code} inattendu"
    result["statut"] = "doublon" if any("déjà dans la collection" in e.lower() for e in errors) else "erreur"
    result["detail"] = message
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Import en masse de DVD depuis un CSV, via l'API HTTP de l'application (aucun accès direct au conteneur requis)"
    )
    parser.add_argument("csv_path", type=Path, help="Fichier CSV à importer (colonnes titre, couleur)")
    parser.add_argument(
        "--base-url",
        required=True,
        help="URL de base de l'application, ex: http://localhost:5000 ou https://cineroulette.home",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="N'envoie rien à l'application : prévisualise juste les correspondances trouvées"
    )
    parser.add_argument("--delay", type=float, default=0.3, help="Délai en secondes entre chaque film (défaut 0.3s)")
    parser.add_argument("--timeout", type=float, default=15, help="Timeout HTTP par requête, en secondes (défaut 15s)")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Ignore la vérification du certificat TLS (utile avec un certificat local type mkcert non reconnu ici)",
    )
    args = parser.parse_args()

    if not args.csv_path.exists():
        print(f"Fichier introuvable : {args.csv_path}")
        sys.exit(1)

    with args.csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        columns = {(name or "").strip().lower(): name for name in (reader.fieldnames or [])}
        if "titre" not in columns or "couleur" not in columns:
            print("Le CSV doit contenir les colonnes 'titre' et 'couleur' (avec en-tête).")
            sys.exit(1)
        rows = list(reader)

    if not rows:
        print("Le CSV ne contient aucune ligne à traiter.")
        sys.exit(0)

    base_url = args.base_url.rstrip("/")
    session = requests.Session()
    if args.insecure:
        session.verify = False
        requests.packages.urllib3.disable_warnings()  # noqa: SLF001

    # Vérifie que l'application répond avant de se lancer dans tout le lot.
    try:
        session.get(f"{base_url}/dvd", timeout=args.timeout).raise_for_status()
    except requests.RequestException as exc:
        print(f"Impossible de joindre l'application sur {base_url} : {exc}")
        sys.exit(1)

    results = []
    mode = " (mode dry-run, rien ne sera envoyé)" if args.dry_run else ""
    print(f"{len(rows)} film(s) à traiter contre {base_url}{mode}...\n")

    for i, row in enumerate(rows, start=1):
        titre = row[columns["titre"]] or ""
        couleur = row[columns["couleur"]] or ""
        result = process_row(session, base_url, args.timeout, i, titre, couleur, args.dry_run)
        results.append(result)
        print(f"[{result['statut']}] {titre} — {result['detail']}")
        if i < len(rows):
            time.sleep(args.delay)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "_dryrun" if args.dry_run else ""
    report_path = args.csv_path.with_name(f"{args.csv_path.stem}_resultat{suffix}_{timestamp}.csv")
    with report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ligne", "titre_saisi", "couleur_saisie", "statut", "detail"])
        writer.writeheader()
        writer.writerows(results)

    counts = {}
    for r in results:
        counts[r["statut"]] = counts.get(r["statut"], 0) + 1

    print("\n--- Résumé ---")
    for statut, count in counts.items():
        print(f"{statut} : {count}")
    print(f"\nRapport détaillé : {report_path}")


if __name__ == "__main__":
    main()
