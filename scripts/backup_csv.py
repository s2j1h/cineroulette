#!/usr/bin/env python3
"""Sauvegarde titre + couleur de toute la collection dans un CSV, via l'API
HTTP de l'application.

Ce script ne touche ni la base de données ni le système de fichiers
directement : il parcourt les pages de /dvd exactement comme le ferait un
navigateur, et en extrait le titre et la couleur de chaque DVD affiché.
Il fonctionne donc aussi bien contre une instance locale (`python run.py`)
que contre l'application déployée dans son conteneur Docker (Portainer).

Le fichier généré est au même format que celui attendu par
scripts/import_csv.py (colonnes "titre" et "couleur", séparées par des
points-virgules), pour permettre de reconstruire rapidement le référentiel
en le réimportant.

Attention : ceci ne sauvegarde que le titre et la couleur, pas le reste
(jaquette, résumé, année, note IMDb, EAN...). En cas de restauration via
import_csv.py, ces informations sont re-récupérées depuis TMDB au moment de
l'import — ce qui peut donner une édition/jaquette légèrement différente de
l'originale, et un titre ambigu ou introuvable au moment de la sauvegarde
redeviendra à traiter à la main comme n'importe quel import.

Usage :
    python scripts/backup_csv.py --base-url http://localhost:5000
    python scripts/backup_csv.py --base-url https://cineroulette.home -o backup.csv
    python scripts/backup_csv.py --base-url https://192.168.1.52:5000 --insecure
"""
import argparse
import csv
import html
import re
import sys
from datetime import datetime
from pathlib import Path

import requests

CARD_RE = re.compile(r'<a class="card".*?</a>', re.DOTALL)
TITLE_RE = re.compile(r"<h3>(.*?)</h3>", re.DOTALL)
COULEUR_RE = re.compile(r'class="pastille"[^>]*title="([^"]*)"')
PAGE_INFO_RE = re.compile(r"Page \d+\s*/\s*(\d+)")


def fetch_page(session, base_url, timeout, page):
    r = session.get(
        f"{base_url}/dvd", params={"page": page}, headers={"X-Requested-With": "fetch"}, timeout=timeout
    )
    r.raise_for_status()
    return r.text


def parse_dvds(page_html):
    dvds = []
    for card_html in CARD_RE.findall(page_html):
        title_match = TITLE_RE.search(card_html)
        couleur_match = COULEUR_RE.search(card_html)
        if not title_match or not couleur_match:
            continue
        titre = html.unescape(title_match.group(1)).strip()
        couleur = html.unescape(couleur_match.group(1)).strip()
        dvds.append((titre, couleur))
    return dvds


def parse_total_pages(page_html):
    m = PAGE_INFO_RE.search(page_html)
    return int(m.group(1)) if m else 1


def main():
    parser = argparse.ArgumentParser(
        description="Sauvegarde titre + couleur de la collection dans un CSV, via l'API HTTP de l'application"
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="URL de base de l'application, ex: http://localhost:5000 ou https://cineroulette.home",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None, help="Chemin du fichier CSV de sortie (défaut: backup_<date>.csv)"
    )
    parser.add_argument("--timeout", type=float, default=15, help="Timeout HTTP par requête, en secondes (défaut 15s)")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Ignore la vérification du certificat TLS (utile avec un certificat local type mkcert non reconnu ici)",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    session = requests.Session()
    if args.insecure:
        session.verify = False
        requests.packages.urllib3.disable_warnings()  # noqa: SLF001

    try:
        first_page_html = fetch_page(session, base_url, args.timeout, 1)
    except requests.RequestException as exc:
        print(f"Impossible de joindre l'application sur {base_url} : {exc}")
        sys.exit(1)

    total_pages = parse_total_pages(first_page_html)
    dvds = parse_dvds(first_page_html)

    for page in range(2, total_pages + 1):
        try:
            page_html = fetch_page(session, base_url, args.timeout, page)
        except requests.RequestException as exc:
            print(f"Échec de récupération de la page {page} : {exc}")
            sys.exit(1)
        dvds.extend(parse_dvds(page_html))

    output_path = args.output or Path(f"backup_{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv")
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["titre", "couleur"])
        writer.writerows(dvds)

    print(f"{len(dvds)} DVD sauvegardé(s) dans {output_path}")


if __name__ == "__main__":
    main()
