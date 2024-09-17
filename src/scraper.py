import base64
import hashlib
import json
import os
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

BASE_URL = "https://www.screenscraper.fr/api2/jeuInfos.php"
MAX_FILE_SIZE_BYTES = 104857600  # 100MB


class ScraperError(Exception):
    pass


class UnreadableBodyError(ScraperError):
    pass


class EmptyBodyError(ScraperError):
    pass


class GameNotFoundError(ScraperError):
    pass


class APIClosedError(ScraperError):
    pass


class HTTPRequestError(ScraperError):
    pass


class UnknownMediaTypeError(ScraperError):
    pass


def get_image_files_without_extension(folder):
    image_extensions = (".jpg", ".jpeg", ".png")
    return [f.stem for f in folder.glob("*") if f.suffix.lower() in image_extensions]


def sha1sum(file_path):
    if os.path.getsize(file_path) > MAX_FILE_SIZE_BYTES:
        return ""

    hash_sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha1.update(chunk)
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
    return os.path.getsize(file_path)


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
        "romnom": clean_rom_name(rom_path) + ".zip",
        "romtaille": str(file_size(rom_path)),
    }

    url_parts = list(urlparse(BASE_URL))
    query = urlencode(params)
    url_parts[4] = query
    return urlunparse(url_parts)


def find_media_url_by_region(medias, media_type, regions):
    for region in regions:
        for media in medias:
            if media["type"] == media_type and media["region"] == region:
                return media["url"]

    raise ScraperError(f"Media not found for regions: {regions}")


def add_wh_to_media_url(media_url, width, height):
    parsed_url = urlparse(media_url)
    query = parse_qs(parsed_url.query)
    query["maxwidth"] = [str(width)]
    query["maxheight"] = [str(height)]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed_url._replace(query=new_query))


def check_media_type(media_type):
    if media_type not in [
        "box-2D",
        "box-3D",
        "mixrbv1",
        "mixrbv2",
    ]:
        raise UnknownMediaTypeError("Unknown media type")


def check_destination(dest):
    if os.path.exists(dest):
        raise ScraperError(f"Destination file already exists: {dest}")
    dest_dir = os.path.dirname(dest)
    os.makedirs(dest_dir, exist_ok=True)


def get(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        if isinstance(e, requests.Timeout):
            raise HTTPRequestError("Request aborted")
        raise HTTPRequestError("Error making HTTP request")

    body = response.content
    return body


def find_game(system_id, rom_path, dev_id, dev_password, username, password):
    result = {}
    game_url = parse_find_game_url(
        system_id, rom_path, dev_id, dev_password, username, password
    )

    body = get(game_url)
    body_str = body.decode("utf-8")

    if "API closed" in body_str:
        raise APIClosedError()
    if "Erreur" in body_str:
        raise GameNotFoundError()
    if not body:
        raise EmptyBodyError()
    try:

        result = json.loads(body_str)
    except json.JSONDecodeError:
        raise UnreadableBodyError()

    return result


def download_media(medias, config_media):
    media_type = config_media["type"]
    regions = config_media["regions"]
    width = config_media["width"]
    height = config_media["height"]
    check_media_type(media_type)

    try:
        media_url = find_media_url_by_region(medias, media_type, regions)
        media_url = add_wh_to_media_url(media_url, width, height)
        res = get(media_url)
    except ScraperError as e:
        raise e

    return res
