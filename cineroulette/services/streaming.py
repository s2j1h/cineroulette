import json
import logging
from datetime import timedelta

from flask import current_app

from ..models import StreamingCache, db, utcnow
from . import tmdb

logger = logging.getLogger(__name__)

# TMDB liste des variantes/revendeurs qui font doublon avec la plateforme mère
# (ex. « Netflix Standard with Ads », « HBO Max Amazon Channel »). On les écarte
# pour n'afficher que les plateformes principales.
_VARIANT_MARKERS = ("with ads", "amazon channel", "apple tv channel", "channel")


def _is_variant(name):
    lowered = name.lower()
    return any(marker in lowered for marker in _VARIANT_MARKERS)


def _fetch_flatrate_fr(tmdb_id):
    """Interroge TMDB et extrait les plateformes d'abonnement (flatrate) de la
    région configurée, hors variantes/revendeurs (voir _VARIANT_MARKERS).
    Retourne une liste [{"name", "logo_url"}] (éventuellement vide si le film
    n'y est pas disponible), ou None en cas d'échec d'appel."""
    results = tmdb.get_watch_providers(tmdb_id)
    if results is None:
        return None

    region = current_app.config["STREAMING_REGION"]
    region_data = results.get(region) or {}
    flatrate = region_data.get("flatrate") or []
    flatrate = sorted(flatrate, key=lambda p: p.get("display_priority", 999))

    providers = []
    seen = set()
    for p in flatrate:
        name = p.get("provider_name")
        if not name or _is_variant(name) or name in seen:
            continue
        seen.add(name)
        providers.append(
            {
                "name": name,
                "logo_url": f"{tmdb.WATCH_PROVIDER_LOGO_BASE_URL}{p['logo_path']}"
                if p.get("logo_path")
                else None,
            }
        )
    return providers


def get_flatrate_fr(tmdb_id):
    """Plateformes d'abonnement (région FR) où le film est disponible, via un
    cache local rafraîchi toutes les STREAMING_CACHE_HOURS. Retourne toujours une
    liste (vide si non disponible, sans tmdb_id, ou si l'appel échoue sans cache
    de secours)."""
    if not tmdb_id:
        return []

    cache = StreamingCache.query.filter_by(tmdb_id=tmdb_id).first()
    ttl = timedelta(hours=current_app.config["STREAMING_CACHE_HOURS"])
    if cache and utcnow() - cache.fetched_at < ttl:
        return json.loads(cache.providers)

    providers = _fetch_flatrate_fr(tmdb_id)
    if providers is None:
        # Échec d'appel : on sert le cache périmé s'il existe plutôt que rien.
        if cache:
            logger.warning(
                "Streaming : appel TMDB échoué pour tmdb_id=%s, cache périmé servi", tmdb_id
            )
            return json.loads(cache.providers)
        logger.warning("Streaming : appel TMDB échoué pour tmdb_id=%s, aucun cache", tmdb_id)
        return []

    payload = json.dumps(providers, ensure_ascii=False)
    if cache:
        cache.providers = payload
        cache.fetched_at = utcnow()
    else:
        cache = StreamingCache(tmdb_id=tmdb_id, providers=payload, fetched_at=utcnow())
        db.session.add(cache)
    db.session.commit()
    logger.info("Streaming : %s plateforme(s) FR (flatrate) pour tmdb_id=%s", len(providers), tmdb_id)
    return providers
