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

    UPCITEMDB_API_KEY = os.environ.get("UPCITEMDB_API_KEY", "")
    TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
    OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "")

    UPCITEMDB_DAILY_QUOTA = 100
    UPCITEMDB_QUOTA_WARNING_THRESHOLD = 10

    # Streaming (TMDB watch/providers, données JustWatch) : on ne retient que la
    # région FR et les plateformes d'abonnement (flatrate). Cache rafraîchi
    # toutes les 48 h car les disponibilités changent régulièrement.
    STREAMING_REGION = "FR"
    STREAMING_CACHE_HOURS = 48

    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    COULEURS_VALIDES = ("rouge", "vert", "dorée", "argent")

    SSL_CERT_FILE = os.environ.get("SSL_CERT_FILE", "")
    SSL_KEY_FILE = os.environ.get("SSL_KEY_FILE", "")
