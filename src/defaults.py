"""Hardcoded defaults for Artie Scraper."""

# Paths
ROMS_PATH = "/mnt/sdcard/ROMS"
LOGOS_PATH = "assets/logos"
CATALOGUE_BASE = "/mnt/mmc/MUOS/info/catalogue"

# Theme colors
COLORS = {
    "primary": "#d4881c",
    "primary_dark": "#a06210",
    "secondary": "#1e1e2e",
    "secondary_light": "#2a2a3c",
    "secondary_dark": "#14141e",
}

# Scraper content defaults
BOX_CONFIG = {
    "height": 240,
    "width": 320,
    "apply_mask": False,
    "mask_path": "assets/masks/box_mask.png",
    "resize_mask": True,
}

PREVIEW_CONFIG = {
    "height": 275,
    "width": 515,
    "apply_mask": False,
    "mask_path": "assets/masks/preview_mask.png",
    "resize_mask": True,
}

REGIONS = ["us", "eu", "jp", "br", "ss", "ame", "wor"]

# Default user settings (used when settings.json is missing or incomplete)
DEFAULT_SETTINGS = {
    "username": "",
    "password": "",
    "threads": 10,
    "show_scraped_roms": True,
    "show_logos": True,
    "box_enabled": True,
    "preview_enabled": True,
    "synopsis_enabled": True,
    "synopsis_lang": "en",
    "box_type": "mixrbv2",
    "preview_type": "ss",
    "log_level": "info",
}

# Dev credentials — injected at build time via dev_credentials.py
# For local development, set SS_DEV_ID and SS_DEV_PASSWORD env vars
try:
    from dev_credentials import DEVID, DEVPASSWORD
except ImportError:
    import os

    DEVID = os.environ.get("SS_DEV_ID", "")
    DEVPASSWORD = os.environ.get("SS_DEV_PASSWORD", "")
