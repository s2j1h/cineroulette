from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

COULEURS_VALIDES = ("rouge", "vert", "dorée", "argent")


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_themes(theme):
    """Le champ theme reste une simple chaîne "Action, Aventure, ..." en base
    (pas de table de genres normalisée), mais est manipulé comme une liste de
    hashtags indépendants partout où on l'affiche ou le filtre."""
    if not theme:
        return []
    return [t.strip() for t in theme.split(",") if t.strip()]


class Dvd(db.Model):
    __tablename__ = "dvd"

    id = db.Column(db.Integer, primary_key=True)
    ean = db.Column(db.String(13), unique=True, nullable=True)
    tmdb_id = db.Column(db.Integer, nullable=True)
    titre_fr = db.Column(db.String(255), nullable=False)
    titre_en = db.Column(db.String(255), nullable=True)
    resume = db.Column(db.Text, nullable=True)
    theme = db.Column(db.String(100), nullable=True)
    annee = db.Column(db.Integer, nullable=True)
    note_imdb = db.Column(db.Float, nullable=True)
    jaquette_path = db.Column(db.String(255), nullable=True)
    couleur = db.Column(db.String(20), nullable=False)
    date_ajout = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.CheckConstraint(
            "couleur IN ('rouge', 'vert', 'dorée', 'argent')", name="ck_dvd_couleur"
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "ean": self.ean,
            "tmdb_id": self.tmdb_id,
            "titre_fr": self.titre_fr,
            "titre_en": self.titre_en,
            "resume": self.resume,
            "theme": self.theme,
            "annee": self.annee,
            "note_imdb": self.note_imdb,
            "jaquette_path": self.jaquette_path,
            "couleur": self.couleur,
            "date_ajout": self.date_ajout.isoformat() if self.date_ajout else None,
        }


class StreamingCache(db.Model):
    """Cache local des plateformes de streaming (flatrate/abonnement, région FR)
    renvoyées par TMDB (données JustWatch), pour éviter un appel réseau à chaque
    affichage d'un film et rester sous le rate-limit de l'API.

    Les disponibilités évoluant régulièrement, une entrée est rafraîchie après
    STREAMING_CACHE_HOURS (voir config.py). `providers` est une liste JSON
    d'objets {"name", "logo_url"}, éventuellement vide (film non disponible en
    streaming) — cet état négatif est mis en cache lui aussi."""

    __tablename__ = "streaming_cache"

    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    providers = db.Column(db.Text, nullable=False, default="[]")
    fetched_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class QuotaCounter(db.Model):
    """Suivi local (applicatif) de la consommation du quota UPCitemdb (tier
    gratuit, ~100 requêtes/jour par IP)."""

    __tablename__ = "quota_counter"

    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(50), unique=True, nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)
    period_start = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
