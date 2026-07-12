from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

COULEURS_VALIDES = ("rouge", "bleu", "dorée", "argent")


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Dvd(db.Model):
    __tablename__ = "dvd"

    id = db.Column(db.Integer, primary_key=True)
    ean = db.Column(db.String(13), unique=True, nullable=True)
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
            "couleur IN ('rouge', 'bleu', 'dorée', 'argent')", name="ck_dvd_couleur"
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "ean": self.ean,
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


class QuotaCounter(db.Model):
    """Suivi local (applicatif) de la consommation du quota DVDFr.

    Le reset "manuel" ne fait qu'annuler notre propre compteur local ; il ne
    contacte pas DVDFr (le reset réel se fait sur leur site, cf. §4.2 du cahier
    des charges). resets_used sert juste de rappel visuel du nombre de resets
    déjà consommés sur les 5 autorisés.
    """

    __tablename__ = "quota_counter"

    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(50), unique=True, nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)
    period_start = db.Column(db.DateTime, nullable=False, default=utcnow)
    resets_used = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
