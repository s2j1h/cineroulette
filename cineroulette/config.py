import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'cineroulette.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    COVERS_DIR = BASE_DIR / "cineroulette" / "static" / "covers"
    LOGS_DIR = BASE_DIR / "logs"

    DVDFR_API_KEY = os.environ.get("DVDFR_API_KEY", "")
    TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
    OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "")

    DVDFR_WEEKLY_QUOTA = 200
    DVDFR_QUOTA_WARNING_THRESHOLD = 20
    DVDFR_MAX_MANUAL_RESETS = 5

    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    COULEURS_VALIDES = ("rouge", "bleu", "dorée", "argent")

    SSL_CERT_FILE = os.environ.get("SSL_CERT_FILE", "")
    SSL_KEY_FILE = os.environ.get("SSL_KEY_FILE", "")
