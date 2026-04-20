"""Configuration management module for Artie Scraper."""

import base64
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import exceptions
from defaults import (
    BOX_CONFIG,
    COLORS,
    DEFAULT_SETTINGS,
    DEVID,
    DEVPASSWORD,
    LOGOS_PATH,
    PREVIEW_CONFIG,
    REGIONS,
    ROMS_PATH,
    ROMS_PATH_CANDIDATES,
)
from logger import LoggerSingleton as logger
from systems import build_systems_mapping


@dataclass
class ScraperConfig:
    """Configuration data structure for scraper settings."""

    # Paths
    roms_path: str
    systems_logo_path: str

    # API credentials
    dev_id: str
    dev_password: str
    username: str
    password: str

    # Feature flags
    box_enabled: bool
    preview_enabled: bool
    synopsis_enabled: bool
    video_enabled: bool
    show_scraped_roms: bool
    show_logos: bool
    offline_mode: bool

    # Performance settings
    threads: int

    # Theme
    theme: str

    # Content configuration (passed to scraper functions)
    content: Dict[str, Any]
    systems_mapping: Dict[str, Any]
    colors: Dict[str, str]


SETTINGS_FILE = "settings.json"


class ConfigManager:
    """Manages application configuration from settings.json + hardcoded defaults."""

    DEFAULT_THREAD_COUNT = 10
    MAX_THREAD_COUNT = 20

    def __init__(self):
        self.config: Optional[ScraperConfig] = None
        self.settings: Dict[str, Any] = {}
        self.settings_path: str = ""

    def load_settings(self, settings_dir: str) -> ScraperConfig:
        """Load settings and build configuration.

        Args:
            settings_dir: Directory containing settings.json

        Returns:
            Validated configuration object
        """
        try:
            settings_file = Path(settings_dir) / SETTINGS_FILE
            self.settings_path = str(settings_file.absolute())

            # Load settings.json (or migrate from config.json)
            self.settings = self._load_settings_file(settings_file, settings_dir)

            # Build ScraperConfig from defaults + settings
            self.config = self._build_config()

            logger.log_info(
                f"Configuration loaded: user={self.config.username or '(none)'}, "
                f"threads={self.config.threads}, "
                f"systems={len(self.config.systems_mapping)}"
            )
            return self.config

        except exceptions.ConfigurationError:
            raise
        except Exception as e:
            raise exceptions.ConfigurationError(
                f"Unexpected error loading configuration: {e}"
            )

    def _load_settings_file(
        self, settings_file: Path, settings_dir: str
    ) -> Dict[str, Any]:
        """Load settings.json, migrating from config.json if needed."""
        if settings_file.exists():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.log_info(f"Loaded settings from {settings_file}")
                # Merge with defaults for any missing keys
                return {**DEFAULT_SETTINGS, **data}
            except (json.JSONDecodeError, IOError) as e:
                # settings.json exists but is corrupt. Don't silently drop
                # credentials — move the broken file aside so the user
                # can recover it, and surface the failure loudly in the
                # log. First-launch credential prompt kicks in after.
                backup = settings_file.with_suffix(".json.corrupt")
                try:
                    settings_file.rename(backup)
                    logger.log_error(
                        f"settings.json is corrupt ({e}); moved to {backup.name}. "
                        f"Credentials reset — re-enter them on the settings screen."
                    )
                except OSError as move_err:
                    logger.log_error(
                        f"settings.json corrupt ({e}) and could not be "
                        f"moved aside ({move_err}); using defaults."
                    )

        # Try migrating from old config.json (pre-4.x installs)
        old_config = Path(settings_dir) / "config.json"
        if old_config.exists():
            logger.log_info("Migrating from config.json to settings.json")
            settings = self._migrate_from_config(old_config)
            self._write_settings(settings_file, settings)
            return settings

        logger.log_info("No settings file found, using defaults")
        return dict(DEFAULT_SETTINGS)

    def _migrate_from_config(self, config_path: Path) -> Dict[str, Any]:
        """Extract user settings from old config.json format."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                old = json.load(f)
        except Exception as e:
            logger.log_warning(f"Failed to read old config.json: {e}")
            return dict(DEFAULT_SETTINGS)

        ss = old.get("screenscraper", {})
        content = ss.get("content", {})

        settings = dict(DEFAULT_SETTINGS)
        settings["username"] = ss.get("username", "")
        settings["password"] = ss.get("password", "")
        settings["threads"] = ss.get("threads", 10)
        settings["show_scraped_roms"] = ss.get("show_scraped_roms", True)
        settings["show_logos"] = old.get("show_logos", True)
        settings["box_enabled"] = content.get("box", {}).get("enabled", True)
        settings["preview_enabled"] = content.get("preview", {}).get("enabled", True)
        settings["synopsis_enabled"] = content.get("synopsis", {}).get("enabled", True)
        settings["synopsis_lang"] = content.get("synopsis", {}).get("lang", "en")
        settings["box_type"] = content.get("box", {}).get("type", "mixrbv2")
        settings["box_mask"] = content.get("box", {}).get("apply_mask", False)
        settings["box_mask_path"] = content.get("box", {}).get(
            "mask_path", "assets/masks/box_mask.png"
        )
        settings["preview_type"] = content.get("preview", {}).get("type", "ss")
        settings["preview_mask"] = content.get("preview", {}).get("apply_mask", False)
        settings["preview_mask_path"] = content.get("preview", {}).get(
            "mask_path", "assets/masks/preview_mask.png"
        )
        regions = content.get("regions", ["us", "eu", "jp", "br", "ss", "ame", "wor"])
        if isinstance(regions, list):
            settings["regions"] = ",".join(regions)
        else:
            settings["regions"] = str(regions)
        settings["log_level"] = old.get("log_level", "info")

        logger.log_info("Successfully migrated settings from config.json")
        return settings

    def persist_setting(self, key: str, value: Any) -> None:
        """Update a single setting both in-memory and on disk.

        Used by hotkeys (e.g. SELECT to toggle show_scraped_roms on the
        ROMs screen) where we don't want to drag the user through the
        full settings screen just to flip a boolean.
        """
        self.settings[key] = value
        if self.config is not None and hasattr(self.config, key):
            setattr(self.config, key, value)
        if self.settings_path:
            self._write_settings(Path(self.settings_path), self.settings)

    def _write_settings(self, path: Path, settings: Dict[str, Any]) -> None:
        """Write settings to disk."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
                f.write("\n")
            logger.log_info(f"Settings saved to {path}")
        except Exception as e:
            logger.log_warning(f"Failed to write settings: {e}")

    def _build_config(self) -> ScraperConfig:
        """Build ScraperConfig from settings + hardcoded defaults."""
        s = self.settings

        # Decode dev credentials
        dev_id, dev_password = self._decode_dev_credentials()

        # Thread config
        threads = s.get("threads", self.DEFAULT_THREAD_COUNT)
        if not isinstance(threads, int) or threads < 1:
            threads = self.DEFAULT_THREAD_COUNT
        threads = min(threads, self.MAX_THREAD_COUNT)

        # Build content dict (expected by scraper functions)
        # Regions: stored as comma-separated string, parsed to list
        regions_str = s.get("regions", "us,eu,jp,br,ss,ame,wor")
        if isinstance(regions_str, list):
            regions = regions_str
        else:
            regions = [r.strip() for r in regions_str.split(",") if r.strip()]
        if not regions:
            regions = REGIONS

        content = {
            "box": {
                **BOX_CONFIG,
                "type": s.get("box_type", "mixrbv2"),
                "enabled": s.get("box_enabled", True),
                "apply_mask": s.get("box_mask", False),
                "mask_path": s.get("box_mask_path", BOX_CONFIG["mask_path"]),
            },
            "preview": {
                **PREVIEW_CONFIG,
                "type": s.get("preview_type", "ss"),
                "enabled": s.get("preview_enabled", True),
                "apply_mask": s.get("preview_mask", False),
                "mask_path": s.get("preview_mask_path", PREVIEW_CONFIG["mask_path"]),
            },
            "synopsis": {
                "enabled": s.get("synopsis_enabled", True),
                "lang": s.get("synopsis_lang", "en"),
            },
            "regions": regions,
        }

        # Systems mapping
        systems_mapping = build_systems_mapping()

        # Auto-detect ROMs path
        roms_path = ROMS_PATH
        for candidate in ROMS_PATH_CANDIDATES:
            if Path(candidate).is_dir():
                roms_path = candidate
                break
        logger.log_info(f"ROMs path: {roms_path}")

        return ScraperConfig(
            roms_path=roms_path,
            systems_logo_path=LOGOS_PATH,
            dev_id=dev_id,
            dev_password=dev_password,
            username=s.get("username", ""),
            password=s.get("password", ""),
            box_enabled=s.get("box_enabled", True),
            preview_enabled=s.get("preview_enabled", True),
            synopsis_enabled=s.get("synopsis_enabled", True),
            video_enabled=s.get("video_enabled", False),
            show_scraped_roms=s.get("show_scraped_roms", True),
            show_logos=s.get("show_logos", True),
            offline_mode=s.get("offline_mode", False),
            threads=threads,
            theme=s.get("theme", "dark"),
            content=content,
            systems_mapping=systems_mapping,
            colors=COLORS,
        )

    def _decode_dev_credentials(self) -> tuple:
        """Decode base64 dev credentials."""
        if not DEVID or not DEVPASSWORD:
            raise exceptions.ConfigurationError(
                "Missing developer credentials. "
                "Set SS_DEV_ID and SS_DEV_PASSWORD environment variables."
            )
        try:
            dev_id = base64.b64decode(DEVID).decode()
            dev_password = base64.b64decode(DEVPASSWORD).decode()
            return dev_id, dev_password
        except Exception as e:
            raise exceptions.ConfigurationError(
                f"Invalid base64 developer credentials: {e}"
            )

    def get_enabled_media_types(self) -> List[str]:
        """Get list of enabled media types."""
        if not self.config:
            return []
        return [
            media
            for media, enabled in [
                ("box", self.config.box_enabled),
                ("preview", self.config.preview_enabled),
                ("synopsis", self.config.synopsis_enabled),
            ]
            if enabled
        ]

    def validate_paths(self) -> bool:
        """Validate that configured paths exist and are accessible."""
        if not self.config:
            return False

        roms_path = Path(self.config.roms_path)
        if not roms_path.exists():
            raise exceptions.ConfigurationError(
                f"ROMs path does not exist: {self.config.roms_path}"
            )
        if not roms_path.is_dir():
            raise exceptions.ConfigurationError(
                f"ROMs path is not a directory: {self.config.roms_path}"
            )
        if not any(roms_path.iterdir()):
            raise exceptions.ConfigurationError(
                f"ROMs path is empty: {self.config.roms_path}"
            )

        logos_path = Path(self.config.systems_logo_path)
        if not logos_path.exists():
            logger.log_warning(
                f"Logos path does not exist: {self.config.systems_logo_path}"
            )

        return True

    def update_systems_from_api(self) -> None:
        """Update systems mapping with latest API data."""
        if not self.config:
            return

        try:
            from systems_api import (
                build_dynamic_system_mapping,
                get_systems_list,
                merge_system_mappings,
            )

            logger.log_info("Updating systems mapping from ScreenScraper API")

            api_systems = get_systems_list(
                self.config.dev_id,
                self.config.dev_password,
                self.config.username,
                self.config.password,
            )

            if api_systems:
                dynamic_mapping = build_dynamic_system_mapping(api_systems)
                if dynamic_mapping:
                    self.config.systems_mapping = merge_system_mappings(
                        self.config.systems_mapping, dynamic_mapping
                    )
                    logger.log_info(
                        f"Updated systems mapping: {len(self.config.systems_mapping)} systems"
                    )

        except exceptions.RateLimitError as e:
            logger.log_warning(f"Rate limited updating systems: {e}")
        except exceptions.ForbiddenError as e:
            logger.log_warning(f"Forbidden updating systems: {e}")
        except exceptions.NetworkError as e:
            logger.log_warning(f"Network error updating systems: {e}")
        except Exception as e:
            logger.log_error(f"Error updating systems from API: {e}")

    def setup_logging(self) -> None:
        """Setup logging based on settings."""
        log_level_str = self.settings.get("log_level", "INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
        logger.setup_logger(log_level)

    def validate_mask_settings(self) -> None:
        """Validate mask settings in configuration."""
        if not self.config:
            return

        try:
            from image_processor import get_image_processor

            image_processor = get_image_processor()
            content = self.config.content

            for media_type in ("box", "preview"):
                cfg = content.get(media_type, {})
                if cfg.get("apply_mask", False):
                    mask_path = cfg.get("mask_path")
                    if mask_path and not image_processor.validate_mask_file(mask_path):
                        logger.log_warning(
                            f"{media_type} mask validation failed: {mask_path}"
                        )

        except Exception as e:
            logger.log_warning(f"Error validating mask settings: {e}")
