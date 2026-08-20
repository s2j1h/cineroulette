import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

# Doit être chargé avant l'import de .config : les attributs de Config sont lus
# depuis os.environ à l'import du module, donc le .env doit déjà être en place.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from flask import Flask, url_for

from .config import Config
from .models import db, parse_themes, QuotaCounter


def setup_logging(app):
    log_level = logging.DEBUG if app.debug else logging.INFO
    log_format = "%(asctime)s | %(levelname)s | %(module)s | %(message)s"
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    app.config["LOGS_DIR"].mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        app.config["LOGS_DIR"] / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)

    if app.debug:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)

    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.setLevel(logging.WARNING)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    setup_logging(app)

    app.config["COVERS_DIR"].mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        for service in ("upcitemdb",):
            if not QuotaCounter.query.filter_by(service=service).first():
                db.session.add(QuotaCounter(service=service))
        db.session.commit()

    from .routes.dvd import dvd_bp
    from .routes.roulette import roulette_bp

    app.register_blueprint(dvd_bp)
    app.register_blueprint(roulette_bp)

    app.jinja_env.filters["theme_list"] = parse_themes

    @app.route("/")
    def index():
        from flask import redirect, url_for

        return redirect(url_for("dvd.list_dvd"))

    @app.context_processor
    def inject_globals():
        return {
            "couleur_hex": {
                "rouge": "#c0392b",
                "vert": "#3fae66",
                "dorée": "#caa63d",
                "argent": "#9aa0a6",
            }
        }

    def dated_url_for(endpoint, **values):
        """Ajoute un suffixe `?v=<mtime>` aux URLs de fichiers statiques pour
        forcer navigateurs et proxys à re-télécharger un asset dès qu'il change
        (fini les CSS/JS périmés après une mise à jour). Le suffixe évolue avec
        la date de modification du fichier ; s'il est introuvable, on renvoie
        l'URL nue sans échouer."""
        if endpoint == "static":
            filename = values.get("filename")
            if filename:
                file_path = os.path.join(app.static_folder, filename)
                try:
                    values["v"] = int(os.stat(file_path).st_mtime)
                except OSError:
                    pass
        return url_for(endpoint, **values)

    @app.context_processor
    def override_url_for():
        # Remplace url_for dans les templates par la variante horodatée ci-dessus.
        return {"url_for": dated_url_for}

    logging.getLogger(__name__).info("Application Ciné-Roulette démarrée (debug=%s)", app.debug)

    return app
