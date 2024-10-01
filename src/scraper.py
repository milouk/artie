import base64
import hashlib
import json
import os
import re
import logging
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from pathlib import Path

import requests

BASE_URL = "https://www.screenscraper.fr/api2/jeuInfos.php"
MAX_FILE_SIZE_BYTES = 104857600  # 100MB
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
VALID_MEDIA_TYPES = {"box-2D", "box-3D", "mixrbv1", "mixrbv2", "ss"}


def configure_logging():
    logging.basicConfig(
        level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s"
    )


configure_logging()


def get_image_files_without_extension(folder):
    return [
        f.stem for f in Path(folder).glob("*") if f.suffix.lower() in IMAGE_EXTENSIONS
    ]


def sha1sum(file_path):
    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE_BYTES:
        logging.warning(f"File {file_path} exceeds max file size limit.")
        return ""

    hash_sha1 = hashlib.sha1()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha1.update(chunk)
    except IOError as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return ""
    return hash_sha1.hexdigest()


def clean_rom_name(file_path):
    file_name = os.path.basename(file_path)
    cleaned_name = re.sub(
        r"(\.nkit|!|&|Disc |Rev |-|\s*\([^()]*\)|\s*\[[^\[\]]*\])",
        " ",
        os.path.splitext(file_name)[0],
    )
    return re.sub(r"\s+", " ", cleaned_name).strip()


def file_size(file_path):
    try:
        return os.path.getsize(file_path)
    except OSError as e:
        logging.error(f"Error getting size of file {file_path}: {e}")
        return None


def parse_find_game_url(system_id, rom_path, dev_id, dev_password, username, password):
    params = {
        "devid": base64.b64decode(dev_id).decode(),
        "devpassword": base64.b64decode(dev_password).decode(),
        "softname": "crossmix",
        "output": "json",
        "ssid": username,
        "sspassword": password,
        "sha1": sha1sum(rom_path),
        "systemeid": system_id,
        "romtype": "rom",
        "romnom": f"{clean_rom_name(rom_path)}.zip",
        "romtaille": str(file_size(rom_path)),
    }
    return urlunparse(urlparse(BASE_URL)._replace(query=urlencode(params)))


def find_media_url_by_region(medias, media_type, regions):
    for region in regions:
        for media in medias:
            if media["type"] == media_type and media["region"] == region:
                return media["url"]
    logging.error(f"Media not found for regions: {regions}")
    return None


def add_wh_to_media_url(media_url, width, height):
    parsed_url = urlparse(media_url)
    query = parse_qs(parsed_url.query)
    query.update({"maxwidth": [str(width)], "maxheight": [str(height)]})
    return urlunparse(parsed_url._replace(query=urlencode(query, doseq=True)))


def is_media_type_valid(media_type):
    if media_type not in VALID_MEDIA_TYPES:
        logging.error(f"Unknown media type: {media_type}")
        return False
    return True


def check_destination(dest):
    if os.path.exists(dest):
        logging.error(f"Destination file already exists: {dest}")
        return None
    dest_dir = os.path.dirname(dest)
    try:
        os.makedirs(dest_dir, exist_ok=True)
    except OSError as e:
        logging.error(f"Error creating directory {dest_dir}: {e}")
        return None


def get(url):
    with requests.Session() as session:
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
        except requests.Timeout:
            logging.error("Request timed out")
            return None
        except requests.RequestException as e:
            logging.error(f"Error making HTTP request: {e}")
            return None
        return response.content


def find_game(system_id, rom_path, dev_id, dev_password, username, password):
    game_url = parse_find_game_url(
        system_id, rom_path, dev_id, dev_password, username, password
    )
    try:
        body = get(game_url)
    except Exception as e:
        logging.error(f"Error fetching game data: {e}")
        return None

    if not body:
        return None

    body_str = body.decode("utf-8")
    if "API closed" in body_str:
        logging.error("API is closed")
        return None
    if "Erreur" in body_str:
        logging.error("Game not found")
        return None
    if not body:
        logging.error("Empty response body")
        return None

    try:
        return json.loads(body_str)
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON response: {e}")
        return None


def fetch_art(game, config):
    def fetch_media(medias, properties, regions):
        media_type = properties["type"]
        media_height = properties["height"]
        media_width = properties["width"]

        if not is_media_type_valid(media_type):
            return None

        media_url = find_media_url_by_region(medias, media_type, regions)
        if media_url:
            media_url = add_wh_to_media_url(media_url, media_width, media_height)
            return get(media_url)
        return None

    medias = game["response"]["jeu"]["medias"]
    regions = config.get("regions", ["us", "ame", "wor"])
    box = fetch_media(medias, config["box"], regions)
    preview = fetch_media(medias, config["preview"], regions)

    if not box and not preview:
        logging.error(f"Error downloading media: {medias}")
        return None, None

    return box, preview


def fetch_synopsis(game, config):
    synopsis = game["response"]["jeu"].get("synopsis")
    if not synopsis:
        return None

    synopsis_lang = config["synopsis"]["lang"]
    synopsis_text = next(
        (item["text"] for item in synopsis if item["langue"] == synopsis_lang), None
    )
    if synopsis_text:
        return synopsis_text
    return None
