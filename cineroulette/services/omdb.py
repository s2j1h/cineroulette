import logging

import requests
from flask import current_app

logger = logging.getLogger(__name__)

OMDB_URL = "https://www.omdbapi.com/"


def get_rating(imdb_id):
    if not imdb_id:
        return None

    api_key = current_app.config["OMDB_API_KEY"]
    if not api_key:
        logger.warning("Clé API OMDb absente, appel ignoré pour %s", imdb_id)
        return None

    try:
        logger.debug("Appel OMDb i=%s", imdb_id)
        response = requests.get(OMDB_URL, params={"i": imdb_id, "apikey": api_key}, timeout=8)
    except requests.RequestException as exc:
        logger.error("Échec appel OMDb pour %s : %s", imdb_id, exc)
        return None

    if response.status_code != 200:
        logger.error("Réponse OMDb non-200 (%s) pour %s", response.status_code, imdb_id)
        return None

    try:
        data = response.json()
    except ValueError:
        logger.error("Réponse OMDb illisible (JSON invalide) pour %s", imdb_id)
        return None

    rating = data.get("imdbRating")
    if not rating or rating == "N/A":
        logger.warning("OMDb : pas de note IMDb disponible pour %s", imdb_id)
        return None

    try:
        return float(rating)
    except ValueError:
        logger.warning("OMDb : note IMDb illisible ('%s') pour %s", rating, imdb_id)
        return None
