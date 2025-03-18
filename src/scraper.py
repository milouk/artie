import base64
import hashlib
import html
import json
import os
import re
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import exceptions
import requests
from logger import LoggerSingleton as logger

GAME_INFO_URL = "https://api.screenscraper.fr/api2/jeuInfos.php"
USER_INFO_URL = "https://api.screenscraper.fr/api2/ssuserInfos.php"
MAX_FILE_SIZE_BYTES = 104857600  # 100MB
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VALID_MEDIA_TYPES = {"box-2D", "box-3D", "mixrbv1", "mixrbv2", "ss", "marquee"}


def get_image_files_without_extension(folder: str) -> List[str]:
    return [
        f.stem for f in Path(folder).glob("*") if f.suffix.lower() in IMAGE_EXTENSIONS
    ]


def get_txt_files_without_extension(folder: str) -> List[str]:
    return [f.stem for f in Path(folder).glob("*.txt")]


def sha1sum(file_path: str) -> str:
    file_size_bytes = os.path.getsize(file_path)
    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        raise exceptions.ScraperError(f"File {file_path} exceeds max file size limit.")

    hash_sha1 = hashlib.sha1()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha1.update(chunk)
    except IOError as e:
        raise exceptions.ScraperError(f"Error reading file {file_path}: {e}")

    return hash_sha1.hexdigest()


def clean_rom_name(file_path: str) -> str:
    file_name = os.path.basename(file_path)
    cleaned = re.sub(
        r"(\.nkit|!|&|Disc |Rev |-|\s*\([^()]*\)|\s*\[[^\[\]]*\])",
        " ",
        os.path.splitext(file_name)[0],
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def file_size(file_path: str) -> int:
    try:
        return os.path.getsize(file_path)
    except OSError as e:
        raise exceptions.ScraperError(f"Error getting size of file {file_path}: {e}")


def parse_find_game_url(
    system_id: str,
    rom_path: str,
    dev_id: str,
    dev_password: str,
    username: str,
    password: str,
) -> str:
    try:
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
        return urlunparse(urlparse(GAME_INFO_URL)._replace(query=urlencode(params)))
    except (UnicodeDecodeError, exceptions.ScraperError) as e:
        logger.log_debug(f"Params: {params}")
        raise exceptions.ScraperError(f"Error encoding URL: {e}. ROM params: {params}")


def parse_user_info_url(
    dev_id: str, dev_password: str, username: str, password: str
) -> str:
    try:
        params = {
            "devid": base64.b64decode(dev_id).decode(),
            "devpassword": base64.b64decode(dev_password).decode(),
            "softname": "crossmix",
            "output": "json",
            "ssid": username,
            "sspassword": password,
        }
        return urlunparse(urlparse(USER_INFO_URL)._replace(query=urlencode(params)))
    except UnicodeDecodeError as e:
        raise exceptions.ScraperError(
            f"Error encoding URL: {e}. User info params: {params}"
        )


def find_media_url_by_region(
    medias: List[dict], media_type: str, regions: List[str]
) -> str:
    for region in regions:
        for media in medias:
            if media.get("type") == media_type and media.get("region") == region:
                url = media.get("url")
                if url is None:
                    raise exceptions.ScraperError(
                        f"Media URL not found for type '{media_type}' and region '{region}'"
                    )
                return url
    raise exceptions.ScraperError(
        f"Media of type '{media_type}' not found for regions: {regions}"
    )


def add_wh_to_media_url(media_url: str, width: int, height: int) -> str:
    parsed = urlparse(media_url)
    query = parse_qs(parsed.query)
    query.update({"maxwidth": [str(width)], "maxheight": [str(height)]})
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def is_media_type_valid(media_type: str) -> bool:
    if media_type not in VALID_MEDIA_TYPES:
        raise exceptions.ScraperError(f"Unknown media type: {media_type}")
    return True


def check_destination(dest: str) -> None:
    dest_dir = os.path.dirname(dest)
    try:
        os.makedirs(dest_dir, exist_ok=True)
    except OSError as e:
        raise exceptions.ScraperError(f"Error creating directory {dest_dir}: {e}")


def get(url: str) -> bytes:
    with requests.Session() as session:
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
            return response.content
        except requests.Timeout:
            raise exceptions.ScraperError("Request timed out")
        except requests.HTTPError as e:
            status = e.response.status_code
            if status == 403:
                raise exceptions.ForbiddenError("Forbidden request")
            elif status == 430:
                raise exceptions.RateLimitError("Rate Limit Exceeded")
            else:
                raise exceptions.ScraperError(f"HTTP error: {e}")
        except requests.RequestException as e:
            raise exceptions.ScraperError(f"HTTP request failed: {e}")


def fetch_data(url: str) -> Any:
    body = get(url)
    body_str = body.decode("utf-8")

    if not body_str:
        raise exceptions.ScraperError("Empty response body")
    if any(err in body_str for err in ["API closed", "Erreur"]):
        raise exceptions.ScraperError(f"Error found in response: {body_str}")
    try:
        return json.loads(body_str)
    except json.JSONDecodeError as e:
        raise exceptions.ScraperError(f"JSON decode error: {e}")


def get_game_data(
    system_id: str,
    rom_path: str,
    dev_id: str,
    dev_password: str,
    username: str,
    password: str,
) -> Any:
    game_url = parse_find_game_url(
        system_id, rom_path, dev_id, dev_password, username, password
    )
    return fetch_data(game_url)


def get_user_data(dev_id: str, dev_password: str, username: str, password: str) -> Any:
    user_info_url = parse_user_info_url(dev_id, dev_password, username, password)
    return fetch_data(user_info_url)


def _fetch_media(medias: List[dict], properties: dict, regions: List[str]) -> bytes:
    media_type = properties["type"]
    media_height = properties["height"]
    media_width = properties["width"]

    is_media_type_valid(media_type)
    media_url = find_media_url_by_region(medias, media_type, regions)
    media_url = add_wh_to_media_url(media_url, media_width, media_height)
    return get(media_url)


def fetch_box(game: dict, config: dict) -> Optional[bytes]:
    medias = game["response"]["jeu"]["medias"]
    regions = config.get("regions", ["us", "ame", "wor"])
    try:
        box = _fetch_media(medias, config["box"], regions)
        return box
    except exceptions.ScraperError as e:
        raise exceptions.ScraperError(f"Error downloading box: {e}")


def fetch_preview(game: dict, config: dict) -> Optional[bytes]:
    medias = game["response"]["jeu"]["medias"]
    regions = config.get("regions", ["us", "ame", "wor"])
    try:
        preview = _fetch_media(medias, config["preview"], regions)
        return preview
    except exceptions.ScraperError as e:
        raise exceptions.ScraperError(f"Error downloading preview: {e}")


def fetch_synopsis(game: dict, config: dict) -> Optional[str]:
    synopsis = game["response"]["jeu"].get("synopsis")
    if not synopsis:
        return None

    synopsis_lang = config["synopsis"]["lang"]
    synopsis_text = next(
        (item["text"] for item in synopsis if item.get("langue") == synopsis_lang), None
    )
    if synopsis_text:
        return html.unescape(synopsis_text)
    return None
