"""Hardcoded defaults for Artie Scraper."""

# Paths — checked in order; first existing path wins
ROMS_PATH_CANDIDATES = [
    "/mnt/sdcard/ROMS",
    "/mnt/mmc/ROMS",
]
ROMS_PATH = "/mnt/sdcard/ROMS"  # fallback default
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

THEMES = {
    "dark": {
        "primary": "#d4881c",
        "primary_dark": "#a06210",
        "white": "#e8e8ec",
        "black": "#0a0a12",
        "muted": "#6c6c80",
        "success": "#4caf50",
        "accent_bar": "#d4881c",
        "row_hover": "#252538",
        "header_bg": "#181824",
        "secondary": "#1e1e2e",
        "secondary_light": "#2a2a3c",
        "secondary_dark": "#14141e",
    },
    "light": {
        "primary": "#c07818",
        "primary_dark": "#8a5510",
        "white": "#1a1a2e",
        "black": "#f0f0f4",
        "muted": "#707088",
        "success": "#388e3c",
        "accent_bar": "#c07818",
        "row_hover": "#d8d8e4",
        "header_bg": "#e0e0ec",
        "secondary": "#c8c8d8",
        "secondary_light": "#d0d0dc",
        "secondary_dark": "#e8e8f0",
    },
}

# Scraper content defaults
BOX_CONFIG = {
    "height": 240,
    "width": 320,
    "apply_mask": False,
    "mask_path": "assets/masks/gradient_1.png",
    "resize_mask": True,
}

PREVIEW_CONFIG = {
    "height": 275,
    "width": 515,
    "apply_mask": False,
    "mask_path": "assets/masks/gradient_1.png",
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
    "box_type": "mixrbv2",
    "box_mask": False,
    "box_mask_path": "assets/masks/gradient_1.png",
    "preview_enabled": True,
    "preview_type": "ss",
    "preview_mask": False,
    "preview_mask_path": "assets/masks/gradient_1.png",
    "synopsis_enabled": True,
    "synopsis_lang": "en",
    "regions": "us,eu,jp,br,ss,ame,wor",
    "log_level": "info",
    "theme": "dark",
    "video_enabled": False,
    "offline_mode": False,
}

# Dev credentials — injected at build time via dev_credentials.py
# For local development, set SS_DEV_ID and SS_DEV_PASSWORD env vars
try:
    from dev_credentials import DEVID, DEVPASSWORD
except ImportError:
    import os

    DEVID = os.environ.get("SS_DEV_ID", "")
    DEVPASSWORD = os.environ.get("SS_DEV_PASSWORD", "")
