import logging

import requests
from flask import current_app

from . import quota

logger = logging.getLogger(__name__)

DVDFR_URL = "http://www.dvdfr.com/api/productlist.php"


def _extract_products(data):
    """La forme exacte de la réponse DVDFr varie selon les comptes/versions
    de l'API ; on essaie plusieurs structures raisonnables plutôt que de
    supposer un format unique."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("products", "results", "items"):
            if isinstance(data.get(key), list):
                return data[key]
        # dict indexé par id ex: {"12345": {...}}
        values = [v for v in data.values() if isinstance(v, dict)]
        if values:
            return values
    return []


def _extract_year(item):
    for key in ("annee", "year", "date_sortie", "date"):
        value = item.get(key)
        if not value:
            continue
        text = str(value)
        for token in text.replace("-", " ").replace("/", " ").split():
            if token.isdigit() and len(token) == 4:
                return int(token)
    return None


def lookup_by_ean(ean):
    """Interroge DVDFr pour un EAN donné. Retourne un dict pré-normalisé
    (titre_fr, jaquette_url, annee) ou None si absent / quota dépassé / erreur."""
    api_key = current_app.config["DVDFR_API_KEY"]
    if not api_key:
        logger.warning("Clé API DVDFr absente, appel DVDFr ignoré pour EAN %s", ean)
        return None

    if not quota.has_quota("dvdfr"):
        logger.warning("Quota DVDFr épuisé, appel ignoré pour EAN %s (bascule fallback manuel)", ean)
        return None

    params = {"ean": ean, "key": api_key, "format": "json"}
    try:
        logger.debug("Appel DVDFr productlist.php ean=%s", ean)
        response = requests.get(DVDFR_URL, params=params, timeout=8)
    except requests.RequestException as exc:
        logger.error("Échec appel DVDFr pour EAN %s : %s", ean, exc)
        return None

    quota.increment("dvdfr")

    if response.status_code == 403 or response.status_code == 429:
        logger.error("Quota DVDFr dépassé selon l'API (HTTP %s) pour EAN %s", response.status_code, ean)
        return None
    if response.status_code != 200:
        logger.error("Réponse DVDFr non-200 (%s) pour EAN %s", response.status_code, ean)
        return None

    try:
        data = response.json()
    except ValueError:
        logger.error("Réponse DVDFr illisible (JSON invalide) pour EAN %s", ean)
        return None

    products = _extract_products(data)
    if not products:
        logger.warning("Aucune fiche DVDFr trouvée pour EAN %s", ean)
        return None

    item = products[0]
    titre_fr = item.get("titre") or item.get("title")
    jaquette_url = item.get("jaquette") or item.get("image") or item.get("cover")

    if not titre_fr:
        logger.warning("Fiche DVDFr trouvée pour EAN %s mais champ titre non reconnu : %s", ean, item)
        return None

    logger.info("DVDFr : fiche trouvée pour EAN %s -> %s", ean, titre_fr)
    return {
        "titre_fr": titre_fr,
        "jaquette_url": jaquette_url,
        "annee": _extract_year(item),
    }
