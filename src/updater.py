"""OTA update module - checks GitHub releases for newer versions."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import requests

from logger import LoggerSingleton as logger

GITHUB_API_URL = "https://api.github.com/repos/milouk/artie/releases/latest"
ASSET_NAME = "Artie.muxapp"


def check_for_update(current_version: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check GitHub for a newer release.

    Returns:
        (update_available, latest_version, download_url)
    """
    try:
        resp = requests.get(GITHUB_API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        tag = data.get("tag_name", "")
        latest_version = tag.lstrip("v")

        if not latest_version:
            return False, None, None

        if _version_newer(latest_version, current_version):
            download_url = None
            for asset in data.get("assets", []):
                if asset.get("name") == ASSET_NAME:
                    download_url = asset.get("browser_download_url")
                    break
            return True, latest_version, download_url

        return False, latest_version, None

    except Exception as e:
        logger.log_warning(f"Update check failed: {e}")
        return False, None, None


def download_and_apply_update(download_url: str) -> bool:
    """
    Download the latest .muxapp and extract it over the current installation.

    Returns:
        True if update was applied successfully
    """
    # Use the SD card for temp files — tmpfs (/tmp) is too small
    app_dir = _get_install_dir()
    tmp_dir = str(app_dir / ".artie") if app_dir else None

    tmp_path = None
    extract_dir = None
    try:
        logger.log_info(f"Downloading update from {download_url}")

        resp = requests.get(download_url, timeout=120, stream=True)
        resp.raise_for_status()

        with tempfile.NamedTemporaryFile(
            suffix=".zip", delete=False, dir=tmp_dir
        ) as tmp:
            tmp_path = tmp.name
            for chunk in resp.iter_content(chunk_size=65536):
                tmp.write(chunk)

        logger.log_info(f"Update downloaded to {tmp_path}")

        # Extract to temp directory on the same filesystem
        extract_dir = tempfile.mkdtemp(dir=tmp_dir)
        shutil.unpack_archive(tmp_path, extract_dir, "zip")

        # Find the Artie directory in the extract
        artie_dir = Path(extract_dir) / "Artie"
        if not artie_dir.exists():
            # Try to find it nested
            for p in Path(extract_dir).rglob("Artie"):
                if p.is_dir():
                    artie_dir = p
                    break

        if not artie_dir.exists():
            logger.log_error("Update archive does not contain Artie directory")
            return False

        if not app_dir:
            logger.log_error("Cannot determine installation directory")
            return False

        # Copy new files over current installation
        src_artie = artie_dir / ".artie"
        if src_artie.exists():
            dst_artie = app_dir / ".artie"
            # Preserve config.json
            config_backup = None
            config_path = dst_artie / "config.json"
            if config_path.exists():
                config_backup = config_path.read_text()

            # Copy new app binary and assets
            for item in src_artie.iterdir():
                dst = dst_artie / item.name
                if item.name == "config.json" and config_backup:
                    continue  # Keep user's config
                if item.is_dir():
                    shutil.copytree(item, dst, dirs_exist_ok=True)
                else:
                    # Remove destination first to avoid ETXTBSY on running binaries
                    if dst.exists():
                        dst.unlink()
                    shutil.copy2(item, dst)

        # Copy new mux_launch.sh
        new_launch = artie_dir / "mux_launch.sh"
        if new_launch.exists():
            shutil.copy2(new_launch, app_dir / "mux_launch.sh")

        # Copy new glyph
        new_glyph = artie_dir / "glyph"
        if new_glyph.exists():
            dst_glyph = app_dir / "glyph"
            shutil.copytree(new_glyph, dst_glyph, dirs_exist_ok=True)

        logger.log_info("Update applied successfully")
        return True

    except Exception as e:
        logger.log_error(f"Failed to apply update: {e}")
        return False

    finally:
        # Always clean up temp files
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if extract_dir:
            try:
                shutil.rmtree(extract_dir)
            except OSError:
                pass


def _get_install_dir() -> Optional[Path]:
    """Get the Artie installation directory."""
    # The app binary runs from .artie/, so parent is the Artie dir
    cwd = Path.cwd()
    if cwd.name == ".artie":
        return cwd.parent
    # Check if we're already in the Artie dir
    if (cwd / ".artie").exists():
        return cwd
    # Fallback: try standard MuOS path
    for mount in ["/run/muos/storage"]:
        standard = Path(mount) / "application" / "Artie"
        if standard.exists():
            return standard
    return None


def _version_newer(latest: str, current: str) -> bool:
    """Compare version strings (e.g. '3.1.0' > '3.0.0')."""
    try:

        def parts(v):
            return [int(x) for x in v.split(".")]

        return parts(latest) > parts(current)
    except (ValueError, AttributeError):
        return False
