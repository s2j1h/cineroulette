import logging

import requests
from flask import current_app

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"
WATCH_PROVIDER_LOGO_BASE_URL = "https://image.tmdb.org/t/p/w92"


def _get(path, params):
    api_key = current_app.config["TMDB_API_KEY"]
    if not api_key:
        logger.warning("Clé API TMDB absente, appel %s ignoré", path)
        return None

    params = {**params, "api_key": api_key}
    try:
        logger.debug("Appel TMDB %s params=%s", path, {k: v for k, v in params.items() if k != "api_key"})
        response = requests.get(f"{BASE_URL}{path}", params=params, timeout=8)
    except requests.RequestException as exc:
        logger.error("Échec appel TMDB %s : %s", path, exc)
        return None

    if response.status_code != 200:
        logger.error("Réponse TMDB non-200 (%s) sur %s", response.status_code, path)
        return None

    try:
        return response.json()
    except ValueError:
        logger.error("Réponse TMDB illisible (JSON invalide) sur %s", path)
        return None


def search_movies(query, max_results=6):
    """Retourne une liste de candidats bruts TMDB (pour choix manuel ou scan)."""
    data = _get("/search/movie", {"query": query, "language": "fr-FR"})
    if not data:
        return []
    results = data.get("results", [])
    if not results:
        logger.warning("TMDB : aucun résultat pour la recherche '%s'", query)
    return results[:max_results]


def get_movie_detail(movie_id):
    data = _get(f"/movie/{movie_id}", {"language": "fr-FR"})
    if not data:
        return None

    genres = [g["name"] for g in data.get("genres", []) if g.get("name")]
    release_date = data.get("release_date") or ""
    annee = int(release_date[:4]) if release_date[:4].isdigit() else None
    poster_path = data.get("poster_path")

    return {
        "titre_fr": data.get("title"),
        "titre_en": data.get("original_title"),
        "resume": data.get("overview") or None,
        "theme": ", ".join(genres) if genres else None,
        "annee": annee,
        "jaquette_url": f"{POSTER_BASE_URL}{poster_path}" if poster_path else None,
        "tmdb_id": data.get("id"),
    }


def get_watch_providers(movie_id):
    """Retourne le dict `results` de TMDB (une entrée par pays) pour les
    plateformes de visionnage, ou None en cas d'erreur réseau/API.

    Un film sans aucune disponibilité renvoie un dict vide (pas None) : l'absence
    de plateforme est une information valide, à distinguer d'un échec d'appel."""
    data = _get(f"/movie/{movie_id}/watch/providers", {})
    if data is None:
        return None
    return data.get("results", {})


def get_external_ids(movie_id):
    data = _get(f"/movie/{movie_id}/external_ids", {})
    if not data:
        return None
    imdb_id = data.get("imdb_id")
    if not imdb_id:
        logger.warning("TMDB : pas d'imdb_id pour le film %s", movie_id)
    return imdb_id
