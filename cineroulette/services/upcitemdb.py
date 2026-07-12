import logging
import re

import requests
from flask import current_app

from . import quota

logger = logging.getLogger(__name__)

TRIAL_URL = "https://api.upcitemdb.com/prod/trial/lookup"
PRO_URL = "https://api.upcitemdb.com/prod/v1/lookup"

# UPCitemdb agrège des fiches de revendeurs (ex: "Pre-Owned The Matrix (Dvd)
# (Good)", "La 5ème Vague [DVD + Copie... Value Guaranteed From Ebay's Biggest
# Seller"), trop bruitées pour la recherche TMDB telles quelles.

# Marqueurs qui annoncent le début du blabla d'annonce revendeur : on tronque le
# titre au premier trouvé plutôt que d'essayer de retirer chaque mention une à une.
_TRUNCATE_MARKERS = [
    r"\[",
    r"\bvalue guaranteed\b",
    r"\bbiggest seller\b",
    r"\bfree shipping\b",
    r"\bfast shipping\b",
    r"\bbrand new sealed\b",
    r"\bregion \d\b",
    r"\bntsc\b",
    r"\bpal\b",
    r"\bfrom ebay\b",
    r"\bship(s|ping)? from\b",
    r"\b\d+\s*(disc|dvd)s?\s*set\b",
]

_NOISE_PATTERNS = [
    r"\bpre-?owned\b",
    r"\blike new\b",
    r"\bbrand new\b",
    r"\bused\b",
    r"\bnew\b",
    r"\bsealed\b",
    r"\(dvd\)",
    r"\(blu-?ray\)",
    r"\(vhs\)",
    r"\(4k\)",
    r"\(good\)",
    r"\(very good\)",
    r"\(acceptable\)",
    r"\(mint\)",
    r"\bdvd\b",
    r"\bblu-?ray\b",
    r"\bwidescreen\b",
    r"\bfullscreen\b",
]


def clean_title_for_search(title):
    """Nettoie un titre de fiche revendeur UPCitemdb pour en faire une requête
    TMDB exploitable : tronque au premier marqueur d'annonce revendeur, puis
    retire les mentions d'état/support isolées restantes."""
    cleaned = title

    earliest_cut = len(cleaned)
    for pattern in _TRUNCATE_MARKERS:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match and match.start() < earliest_cut:
            earliest_cut = match.start()
    cleaned = cleaned[:earliest_cut]

    for pattern in _NOISE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[()\[\]]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:|")
    return cleaned or title


def lookup_by_ean(ean):
    """Interroge UPCitemdb pour un EAN/UPC donné. Retourne un dict pré-normalisé
    (titre, jaquette_url) ou None si absent / quota dépassé / erreur.

    Utilise par défaut l'API "trial" (gratuite, sans clé, ~100 requêtes/jour par
    IP). Si UPCITEMDB_API_KEY est renseignée, bascule sur l'API "PRO" payante —
    vérifier le format exact (header vs query param) dans la doc UPCitemdb au
    moment de l'activer, celle-ci ayant pu évoluer depuis l'écriture de ce code.
    """
    if not quota.has_quota("upcitemdb"):
        logger.warning("Quota UPCitemdb épuisé, appel ignoré pour EAN %s (bascule fallback manuel)", ean)
        return None

    api_key = current_app.config["UPCITEMDB_API_KEY"]
    if api_key:
        url = PRO_URL
        headers = {"user_key": api_key, "key_type": "3scale"}
    else:
        url = TRIAL_URL
        headers = {}

    try:
        logger.debug("Appel UPCitemdb upc=%s", ean)
        response = requests.get(url, params={"upc": ean}, headers=headers, timeout=8)
    except requests.RequestException as exc:
        logger.error("Échec appel UPCitemdb pour EAN %s : %s", ean, exc)
        return None

    quota.increment("upcitemdb")

    if response.status_code == 429:
        logger.error("Quota UPCitemdb dépassé selon l'API (HTTP 429) pour EAN %s", ean)
        return None
    if response.status_code != 200:
        logger.error("Réponse UPCitemdb non-200 (%s) pour EAN %s", response.status_code, ean)
        return None

    try:
        data = response.json()
    except ValueError:
        logger.error("Réponse UPCitemdb illisible (JSON invalide) pour EAN %s", ean)
        return None

    items = data.get("items") or []
    if not items:
        logger.warning("Aucune fiche UPCitemdb trouvée pour EAN %s", ean)
        return None

    item = items[0]
    titre = item.get("title")
    images = item.get("images") or []
    jaquette_url = images[0] if images else None

    if not titre:
        logger.warning("Fiche UPCitemdb trouvée pour EAN %s mais champ titre non reconnu : %s", ean, item)
        return None

    logger.info("UPCitemdb : fiche trouvée pour EAN %s -> %s", ean, titre)
    return {
        "titre": titre,
        "jaquette_url": jaquette_url,
    }
