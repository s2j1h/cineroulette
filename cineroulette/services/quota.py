import logging
from datetime import timedelta

from flask import current_app

from ..models import db, QuotaCounter, utcnow

logger = logging.getLogger(__name__)

WEEK = timedelta(days=7)


def _get_counter(service="dvdfr"):
    counter = QuotaCounter.query.filter_by(service=service).first()
    if counter is None:
        counter = QuotaCounter(service=service)
        db.session.add(counter)
        db.session.commit()
    return counter


def _maybe_roll_period(counter):
    if utcnow() - counter.period_start >= WEEK:
        logger.info(
            "Quota %s : nouvelle période hebdomadaire, compteur remis à zéro (était %s)",
            counter.service,
            counter.count,
        )
        counter.count = 0
        counter.period_start = utcnow()
        db.session.commit()


def get_status(service="dvdfr"):
    counter = _get_counter(service)
    _maybe_roll_period(counter)
    weekly_quota = current_app.config["DVDFR_WEEKLY_QUOTA"]
    max_resets = current_app.config["DVDFR_MAX_MANUAL_RESETS"]
    return {
        "service": service,
        "count": counter.count,
        "remaining": max(weekly_quota - counter.count, 0),
        "weekly_quota": weekly_quota,
        "period_start": counter.period_start,
        "resets_used": counter.resets_used,
        "resets_remaining": max(max_resets - counter.resets_used, 0),
    }


def has_quota(service="dvdfr"):
    status = get_status(service)
    return status["remaining"] > 0


def increment(service="dvdfr"):
    counter = _get_counter(service)
    _maybe_roll_period(counter)
    counter.count += 1
    db.session.commit()

    weekly_quota = current_app.config["DVDFR_WEEKLY_QUOTA"]
    threshold = current_app.config["DVDFR_QUOTA_WARNING_THRESHOLD"]
    remaining = weekly_quota - counter.count
    logger.info("Quota %s décrémenté : %s/%s requêtes utilisées", service, counter.count, weekly_quota)
    if 0 <= remaining <= threshold:
        logger.warning(
            "Quota %s bientôt épuisé : %s requêtes restantes sur %s", service, remaining, weekly_quota
        )
    return remaining


def manual_reset(service="dvdfr"):
    counter = _get_counter(service)
    max_resets = current_app.config["DVDFR_MAX_MANUAL_RESETS"]
    if counter.resets_used >= max_resets:
        logger.warning(
            "Reset manuel du quota %s refusé : les %s resets autorisés ont déjà été utilisés",
            service,
            max_resets,
        )
        return False, get_status(service)

    counter.count = 0
    counter.period_start = utcnow()
    counter.resets_used += 1
    db.session.commit()
    logger.info(
        "Reset manuel du compteur de quota %s effectué (%s/%s resets utilisés)",
        service,
        counter.resets_used,
        max_resets,
    )
    return True, get_status(service)
