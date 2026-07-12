import logging
from datetime import timedelta

from flask import current_app

from ..models import db, QuotaCounter, utcnow

logger = logging.getLogger(__name__)

PERIOD = timedelta(days=1)


def _get_counter(service="upcitemdb"):
    counter = QuotaCounter.query.filter_by(service=service).first()
    if counter is None:
        counter = QuotaCounter(service=service)
        db.session.add(counter)
        db.session.commit()
    return counter


def _maybe_roll_period(counter):
    if utcnow() - counter.period_start >= PERIOD:
        logger.info(
            "Quota %s : nouvelle période, compteur remis à zéro (était %s)",
            counter.service,
            counter.count,
        )
        counter.count = 0
        counter.period_start = utcnow()
        db.session.commit()


def get_status(service="upcitemdb"):
    counter = _get_counter(service)
    _maybe_roll_period(counter)
    daily_quota = current_app.config["UPCITEMDB_DAILY_QUOTA"]
    return {
        "service": service,
        "count": counter.count,
        "remaining": max(daily_quota - counter.count, 0),
        "daily_quota": daily_quota,
        "period_start": counter.period_start,
    }


def has_quota(service="upcitemdb"):
    return get_status(service)["remaining"] > 0


def increment(service="upcitemdb"):
    counter = _get_counter(service)
    _maybe_roll_period(counter)
    counter.count += 1
    db.session.commit()

    daily_quota = current_app.config["UPCITEMDB_DAILY_QUOTA"]
    threshold = current_app.config["UPCITEMDB_QUOTA_WARNING_THRESHOLD"]
    remaining = daily_quota - counter.count
    logger.info("Quota %s décrémenté : %s/%s requêtes utilisées", service, counter.count, daily_quota)
    if 0 <= remaining <= threshold:
        logger.warning(
            "Quota %s bientôt épuisé : %s requêtes restantes sur %s", service, remaining, daily_quota
        )
    return remaining
