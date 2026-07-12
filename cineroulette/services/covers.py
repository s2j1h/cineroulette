import io
import logging

import requests
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)


def _save_image_bytes(dvd_id, data, covers_dir):
    try:
        image = Image.open(io.BytesIO(data))
        image = image.convert("RGB")
    except UnidentifiedImageError:
        logger.error("Fichier jaquette illisible (format non reconnu) pour le DVD %s", dvd_id)
        return None

    covers_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{dvd_id}.jpg"
    image.save(covers_dir / filename, "JPEG", quality=88)
    logger.info("Jaquette enregistrée pour le DVD %s", dvd_id)
    return f"covers/{filename}"


def download_cover(dvd_id, url, covers_dir):
    if not url:
        return None
    try:
        logger.debug("Téléchargement jaquette DVD %s depuis %s", dvd_id, url)
        response = requests.get(url, timeout=10)
    except requests.RequestException as exc:
        logger.error("Échec téléchargement jaquette pour le DVD %s : %s", dvd_id, exc)
        return None

    if response.status_code != 200:
        logger.error("Téléchargement jaquette DVD %s : HTTP %s", dvd_id, response.status_code)
        return None

    return _save_image_bytes(dvd_id, response.content, covers_dir)


def save_uploaded_cover(dvd_id, file_storage, covers_dir):
    data = file_storage.read()
    if not data:
        return None
    return _save_image_bytes(dvd_id, data, covers_dir)
