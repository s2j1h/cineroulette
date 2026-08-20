import logging

from flask import Blueprint, jsonify, render_template, request, url_for

from ..models import Dvd, db
from ..services import streaming

logger = logging.getLogger(__name__)

roulette_bp = Blueprint("roulette", __name__)


@roulette_bp.route("/roulette")
def roulette_page():
    return render_template("roulette.html")


@roulette_bp.route("/random")
def random_dvd():
    theme = request.args.get("theme") or None
    couleur = request.args.get("couleur") or None
    exclude = request.args.get("exclude", type=int)

    query = Dvd.query
    if theme:
        # theme est un hashtag isolé au sein du champ theme (qui peut en
        # contenir plusieurs, ex: "Action, Aventure, ...").
        query = query.filter(Dvd.theme.ilike(f"%{theme}%"))
    if couleur:
        query = query.filter(Dvd.couleur == couleur)
    if exclude:
        query = query.filter(Dvd.id != exclude)

    dvd = query.order_by(db.func.random()).first()

    if not dvd:
        total_query = Dvd.query
        if theme:
            total_query = total_query.filter(Dvd.theme.ilike(f"%{theme}%"))
        if couleur:
            total_query = total_query.filter(Dvd.couleur == couleur)
        total_count = total_query.count()

        message = (
            "Aucun DVD dans cette catégorie pour l'instant."
            if total_count == 0
            else "Un seul DVD dans cette catégorie pour l'instant."
        )
        logger.info("Roulette : pas de tirage possible (theme=%s couleur=%s exclude=%s)", theme, couleur, exclude)
        return jsonify({"error": "no_more", "message": message})

    data = dvd.to_dict()
    data["jaquette_url"] = url_for("static", filename=dvd.jaquette_path) if dvd.jaquette_path else None
    logger.info("Roulette : tirage id=%s titre=%s", dvd.id, dvd.titre_fr)
    return jsonify(data)


@roulette_bp.route("/streaming/<int:tmdb_id>")
def streaming_providers(tmdb_id):
    """Plateformes d'abonnement (région FR) où le film est disponible. Appelé en
    différé par la fiche détail et la roulette pour ne pas bloquer l'affichage."""
    return jsonify({"providers": streaming.get_flatrate_fr(tmdb_id)})
