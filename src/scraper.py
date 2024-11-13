import base64
import hashlib
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from logger import LoggerSingleton as logger

GAME_INFO_URL = "https://api.screenscraper.fr/api2/jeuInfos.php"
USER_INFO_URL = "https://api.screenscraper.fr/api2/ssuserInfos.php"
MAX_FILE_SIZE_BYTES = 104857600  # 100MB
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png"]
VALID_MEDIA_TYPES = {"box-2D", "box-3D", "mixrbv1", "mixrbv2", "ss", "marquee"}


def get_image_files_without_extension(folder):
    return [
        f.stem for f in Path(folder).glob("*") if f.suffix.lower() in IMAGE_EXTENSIONS
    ]


def get_txt_files_without_extension(folder):
    return [f.stem for f in Path(folder).glob("*") if f.suffix.lower() == ".txt"]


def sha1sum(file_path):
    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE_BYTES:
        logger.log_warning(f"File {file_path} exceeds max file size limit.")
        return ""

    hash_sha1 = hashlib.sha1()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha1.update(chunk)
    except IOError as e:
        logger.log_error(f"Error reading file {file_path}: {e}")
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
        logger.log_error(f"Error getting size of file {file_path}: {e}")
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
    try:
        return urlunparse(urlparse(GAME_INFO_URL)._replace(query=urlencode(params)))
    except UnicodeDecodeError as e:
        logger.log_debug("Params: %s")
        logger.log_error(f"Error encoding URL: {e}. ROM params: {params}")
        return None


def parse_user_info_url(dev_id, dev_password, username, password):
    params = {
        "devid": base64.b64decode(dev_id).decode(),
        "devpassword": base64.b64decode(dev_password).decode(),
        "softname": "crossmix",
        "output": "json",
        "ssid": username,
        "sspassword": password,
    }
    try:
        return urlunparse(urlparse(USER_INFO_URL)._replace(query=urlencode(params)))
    except UnicodeDecodeError as e:
        logger.log_error(f"Error encoding URL: {e}. User info params: {params}")
        return None


def find_media_url_by_region(medias, media_type, regions):
    for region in regions:
        for media in medias:
            if media["type"] == media_type and media["region"] == region:
                return media["url"]
    logger.log_error(f"Media not found for regions: {regions}")
    return None


def add_wh_to_media_url(media_url, width, height):
    parsed_url = urlparse(media_url)
    query = parse_qs(parsed_url.query)
    query.update({"maxwidth": [str(width)], "maxheight": [str(height)]})
    return urlunparse(parsed_url._replace(query=urlencode(query, doseq=True)))


def is_media_type_valid(media_type):
    if media_type not in VALID_MEDIA_TYPES:
        logger.log_error(f"Unknown media type: {media_type}")
        return False
    return True


def check_destination(dest):
    if os.path.exists(dest):
        logger.log_error(f"Destination file already exists: {dest}")
        return None
    dest_dir = os.path.dirname(dest)
    try:
        os.makedirs(dest_dir, exist_ok=True)
    except OSError as e:
        logger.log_error(f"Error creating directory {dest_dir}: {e}")
        return None


def get(url):
    with requests.Session() as session:
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
        except requests.Timeout:
            logger.log_error("Request timed out")
            return None
        except requests.RequestException as e:
            logger.log_error(f"Error making HTTP request: {e}")
            return None
        return response.content


def fetch_data(url):
    try:
        body = get(url)
        if not body:
            logger.log_error("Empty response body")
            return None

        body_str = body.decode("utf-8")
        if "API closed" in body_str:
            logger.log_error("API is closed")
            return None
        if "Erreur" in body_str:
            logger.log_error("Error found in response: %s", body_str)
            return None

        return json.loads(body_str)
    except json.JSONDecodeError as e:
        logger.log_error(f"Error decoding JSON response: {e}")
    except Exception as e:
        logger.log_error(f"Error fetching data from URL: {e}")
    return None


def get_game_data(system_id, rom_path, dev_id, dev_password, username, password):
    game_url = parse_find_game_url(
        system_id, rom_path, dev_id, dev_password, username, password
    )
    return fetch_data(game_url)


def get_user_data(dev_id, dev_password, username, password):
    user_info_url = parse_user_info_url(dev_id, dev_password, username, password)
    return fetch_data(user_info_url)


def _fetch_media(medias, properties, regions):
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


def fetch_box(game, config):
    medias = game["response"]["jeu"]["medias"]
    regions = config.get("regions", ["us", "ame", "wor"])
    box = _fetch_media(medias, config["box"], regions)
    if not box:
        logger.log_error(f"Error downloading box: {game['response']['jeu']['medias']}")
        return None
    return box


def fetch_preview(game, config):
    medias = game["response"]["jeu"]["medias"]
    regions = config.get("regions", ["us", "ame", "wor"])
    preview = _fetch_media(medias, config["preview"], regions)
    if not preview:
        logger.log_error(
            f"Error downloading preview: {game['response']['jeu']['medias']}"
        )
        return None
    return preview


def fetch_synopsis(game, config):
    synopsis = game["response"]["jeu"].get("synopsis")
    if not synopsis:
        return None

    synopsis_lang = config["synopsis"]["lang"]
    synopsis_text = next(
        (item["text"] for item in synopsis if item["langue"] == synopsis_lang), None
    )
    if synopsis_text:
        return html.unescape(synopsis_text)
    return None
