import logging
from collections import Counter
from pathlib import Path

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for

from ..models import Dvd, db, parse_themes
from ..services import covers, omdb, quota, tmdb, upcitemdb

logger = logging.getLogger(__name__)

dvd_bp = Blueprint("dvd", __name__, url_prefix="/dvd")

PER_PAGE = 24


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_fetch_request():
    return request.headers.get("X-Requested-With") == "fetch"


def _filtered_query(q, couleur, theme):
    query = Dvd.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Dvd.titre_fr.ilike(like), Dvd.titre_en.ilike(like)))
    if couleur:
        query = query.filter(Dvd.couleur == couleur)
    if theme:
        # theme est un hashtag isolé (ex: "Action") au sein du champ theme qui
        # peut en contenir plusieurs ("Action, Aventure, ..."). Le vocabulaire
        # de genres TMDB ne contient pas de sous-chaînes ambiguës entre tags,
        # une correspondance partielle insensible à la casse suffit donc.
        query = query.filter(Dvd.theme.ilike(f"%{theme}%"))
    return query.order_by(Dvd.titre_fr)


def _known_themes():
    """Retourne les hashtags distincts de la collection avec leur nombre
    d'occurrences, triés par ordre alphabétique."""
    rows = db.session.query(Dvd.theme).filter(Dvd.theme.isnot(None))
    counter = Counter()
    for (theme_str,) in rows:
        counter.update(parse_themes(theme_str))
    return sorted(counter.items())


def _find_duplicate(ean=None, tmdb_id=None, exclude_id=None):
    """Détecte un doublon. L'EAN identifie un exemplaire physique précis (deux
    éditions différentes du même film ont des EAN différents et ne sont donc
    pas des doublons). En l'absence d'EAN (ajout manuel via recherche TMDB),
    le tmdb_id sert de repli pour éviter d'ajouter deux fois le même film."""
    if ean:
        query = Dvd.query.filter_by(ean=ean)
        if exclude_id is not None:
            query = query.filter(Dvd.id != exclude_id)
        found = query.first()
        if found:
            return found
        return None

    if tmdb_id:
        query = Dvd.query.filter_by(tmdb_id=tmdb_id)
        if exclude_id is not None:
            query = query.filter(Dvd.id != exclude_id)
        return query.first()

    return None


@dvd_bp.route("", strict_slashes=False)
def list_dvd():
    q = request.args.get("q", "").strip()
    couleur = request.args.get("couleur") or None
    theme = request.args.get("theme") or None
    page = request.args.get("page", 1, type=int)

    pagination = _filtered_query(q, couleur, theme).paginate(page=page, per_page=PER_PAGE, error_out=False)

    if _is_fetch_request():
        return render_template("_dvd_grid.html", dvds=pagination.items, q=q, couleur=couleur, theme=theme)

    return render_template(
        "dvd_list.html",
        dvds=pagination.items,
        pagination=pagination,
        q=q,
        couleur=couleur,
        theme=theme,
        themes=_known_themes(),
        couleurs=current_app.config["COULEURS_VALIDES"],
    )


@dvd_bp.route("/<int:dvd_id>")
def detail(dvd_id):
    dvd = Dvd.query.get_or_404(dvd_id)
    return render_template("dvd_detail.html", dvd=dvd)


def _apply_cover(dvd, form, files):
    uploaded = files.get("jaquette_file")
    if uploaded and uploaded.filename:
        path = covers.save_uploaded_cover(dvd.id, uploaded, current_app.config["COVERS_DIR"])
        if path:
            dvd.jaquette_path = path
        return

    jaquette_url = form.get("jaquette_url", "").strip()
    if jaquette_url:
        path = covers.download_cover(dvd.id, jaquette_url, current_app.config["COVERS_DIR"])
        if path:
            dvd.jaquette_path = path


@dvd_bp.route("/new", methods=["GET", "POST"])
def new_dvd():
    couleurs = current_app.config["COULEURS_VALIDES"]

    if request.method == "GET":
        return render_template("dvd_form.html", dvd=None, couleurs=couleurs, mode="new", form_data={})

    form = request.form
    titre_fr = form.get("titre_fr", "").strip()
    couleur = form.get("couleur")
    ean = form.get("ean", "").strip() or None
    tmdb_id = _parse_int(form.get("tmdb_id"))

    errors = []
    if not titre_fr:
        errors.append("Le titre français est requis.")
    if couleur not in couleurs:
        errors.append("Merci de choisir une couleur valide.")

    duplicate = _find_duplicate(ean, tmdb_id)
    if duplicate:
        errors.append(
            f"Ce film est déjà dans la collection : « {duplicate.titre_fr} », ajouté "
            f"le {duplicate.date_ajout.strftime('%d/%m/%Y')}."
        )

    if errors:
        for message in errors:
            flash(message, "error")
        return render_template("dvd_form.html", dvd=None, couleurs=couleurs, mode="new", form_data=form), 400

    dvd = Dvd(
        ean=ean,
        tmdb_id=tmdb_id,
        titre_fr=titre_fr,
        titre_en=form.get("titre_en", "").strip() or None,
        resume=form.get("resume", "").strip() or None,
        theme=form.get("theme", "").strip() or None,
        annee=_parse_int(form.get("annee")),
        note_imdb=_parse_float(form.get("note_imdb")),
        couleur=couleur,
    )
    db.session.add(dvd)
    db.session.commit()
    logger.info("DVD ajouté : id=%s titre=%s", dvd.id, dvd.titre_fr)

    _apply_cover(dvd, form, request.files)
    db.session.commit()

    flash(f"« {dvd.titre_fr} » ajouté à la collection.", "success")
    return redirect(url_for("dvd.detail", dvd_id=dvd.id))


@dvd_bp.route("/<int:dvd_id>/edit", methods=["GET", "POST"])
def edit_dvd(dvd_id):
    dvd = Dvd.query.get_or_404(dvd_id)
    couleurs = current_app.config["COULEURS_VALIDES"]

    if request.method == "GET":
        return render_template("dvd_form.html", dvd=dvd, couleurs=couleurs, mode="edit", form_data={})

    form = request.form
    titre_fr = form.get("titre_fr", "").strip()
    couleur = form.get("couleur")
    ean = form.get("ean", "").strip() or None

    errors = []
    if not titre_fr:
        errors.append("Le titre français est requis.")
    if couleur not in couleurs:
        errors.append("Merci de choisir une couleur valide.")

    duplicate = _find_duplicate(ean, exclude_id=dvd.id)
    if duplicate:
        errors.append(
            f"Un autre DVD porte déjà cet EAN dans la collection : « {duplicate.titre_fr} » "
            f"(EAN {ean})."
        )

    if errors:
        for message in errors:
            flash(message, "error")
        return render_template("dvd_form.html", dvd=dvd, couleurs=couleurs, mode="edit", form_data=form), 400

    dvd.ean = ean
    dvd.titre_fr = titre_fr
    dvd.titre_en = form.get("titre_en", "").strip() or None
    dvd.resume = form.get("resume", "").strip() or None
    dvd.theme = form.get("theme", "").strip() or None
    dvd.annee = _parse_int(form.get("annee"))
    dvd.note_imdb = _parse_float(form.get("note_imdb"))
    dvd.couleur = couleur

    _apply_cover(dvd, form, request.files)
    db.session.commit()
    logger.info("DVD modifié : id=%s titre=%s", dvd.id, dvd.titre_fr)

    flash(f"« {dvd.titre_fr} » mis à jour.", "success")
    return redirect(url_for("dvd.detail", dvd_id=dvd.id))


@dvd_bp.route("/<int:dvd_id>/delete", methods=["POST"])
def delete_dvd(dvd_id):
    dvd = Dvd.query.get_or_404(dvd_id)
    titre = dvd.titre_fr

    if dvd.jaquette_path:
        cover_file = current_app.config["COVERS_DIR"] / Path(dvd.jaquette_path).name
        cover_file.unlink(missing_ok=True)

    db.session.delete(dvd)
    db.session.commit()
    logger.info("DVD supprimé : id=%s titre=%s", dvd_id, titre)

    flash(f"« {titre} » supprimé de la collection.", "success")
    return redirect(url_for("dvd.list_dvd"))


def _enrich_from_ean(ean):
    result = {
        "ean": ean,
        "titre_fr": None,
        "titre_en": None,
        "resume": None,
        "theme": None,
        "annee": None,
        "note_imdb": None,
        "jaquette_url": None,
        "source": None,
        "titre_recherche": None,
        "tmdb_id": None,
    }

    barcode_data = upcitemdb.lookup_by_ean(ean)
    titre_query = None
    if barcode_data:
        # Titre provisoire (souvent générique/anglais) : sert de requête pour TMDB
        # ci-dessous, qui fournira le vrai titre français s'il trouve une correspondance.
        result["titre_fr"] = barcode_data.get("titre")
        result["jaquette_url"] = barcode_data.get("jaquette_url")
        result["source"] = "upcitemdb"
        titre_query = upcitemdb.clean_title_for_search(barcode_data.get("titre"))
        result["titre_recherche"] = titre_query
    else:
        flash(
            "EAN non trouvé via UPCitemdb (quota dépassé ou fiche absente) — "
            "recherchez le titre manuellement ci-dessous.",
            "warning",
        )

    if titre_query:
        candidates = tmdb.search_movies(titre_query, max_results=1)
        if candidates:
            detail = tmdb.get_movie_detail(candidates[0]["id"])
            if detail:
                result["titre_fr"] = detail.get("titre_fr") or result["titre_fr"]
                result["titre_en"] = detail.get("titre_en") or result["titre_en"]
                result["resume"] = detail.get("resume") or result["resume"]
                result["theme"] = detail.get("theme") or result["theme"]
                result["annee"] = detail.get("annee") or result["annee"]
                result["jaquette_url"] = result["jaquette_url"] or detail.get("jaquette_url")
                result["tmdb_id"] = detail.get("tmdb_id")
                imdb_id = tmdb.get_external_ids(detail["tmdb_id"])
                if imdb_id:
                    result["note_imdb"] = omdb.get_rating(imdb_id)
        else:
            flash(f"Aucun résultat TMDB pour « {titre_query} ».", "warning")

    return result


@dvd_bp.route("/scan", methods=["GET", "POST"])
def scan_page():
    couleurs = current_app.config["COULEURS_VALIDES"]

    if request.method == "POST":
        ean = request.form.get("ean", "").strip()
        if not ean:
            flash("Aucun code-barre reçu depuis le scan.", "error")
            return redirect(url_for("dvd.scan_page"))

        logger.info("Scan EAN reçu : %s", ean)

        duplicate = _find_duplicate(ean)
        if duplicate:
            logger.info(
                "Scan EAN %s : déjà dans la collection (id=%s titre=%s)", ean, duplicate.id, duplicate.titre_fr
            )
            return render_template(
                "dvd_scan.html",
                quota_status=quota.get_status("upcitemdb"),
                enrichment=None,
                duplicate=duplicate,
                couleurs=couleurs,
            )

        enrichment = _enrich_from_ean(ean)
        return render_template(
            "dvd_scan.html",
            quota_status=quota.get_status("upcitemdb"),
            enrichment=enrichment,
            duplicate=None,
            couleurs=couleurs,
        )

    return render_template(
        "dvd_scan.html",
        quota_status=quota.get_status("upcitemdb"),
        enrichment=None,
        duplicate=None,
        couleurs=couleurs,
    )


@dvd_bp.route("/tmdb_search")
def tmdb_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    candidates = tmdb.search_movies(q, max_results=6)
    return jsonify(
        [
            {
                "id": c.get("id"),
                "titre_fr": c.get("title"),
                "titre_en": c.get("original_title"),
                "annee": (c.get("release_date") or "")[:4],
                "poster_url": f"{tmdb.POSTER_BASE_URL}{c['poster_path']}" if c.get("poster_path") else None,
            }
            for c in candidates
        ]
    )


@dvd_bp.route("/tmdb_pick")
def tmdb_pick():
    movie_id = request.args.get("movie_id", type=int)
    if not movie_id:
        return jsonify({"error": "movie_id manquant"}), 400

    detail = tmdb.get_movie_detail(movie_id)
    if not detail:
        return jsonify({"error": "Film introuvable sur TMDB"}), 404

    imdb_id = tmdb.get_external_ids(movie_id)
    detail["note_imdb"] = omdb.get_rating(imdb_id) if imdb_id else None
    return jsonify(detail)
