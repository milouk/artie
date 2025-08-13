"""Configuration management module for Artie Scraper."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import exceptions
from logger import LoggerSingleton as logger


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
    show_scraped_roms: bool

    # Performance settings
    threads: int

    # Content configuration
    content: Dict[str, Any]
    systems_mapping: Dict[str, Any]
    colors: Dict[str, str]


class ConfigManager:
    """Manages application configuration with validation and error handling."""

    DEFAULT_THREAD_COUNT = 10
    MAX_THREAD_COUNT = 20
    DEFAULT_TIMEOUT = 30

    def __init__(self):
        self.config: Optional[ScraperConfig] = None
        self._raw_config: Dict[str, Any] = {}

    def load_config(self, config_file: str) -> ScraperConfig:
        """
        Load and validate configuration from JSON file.

        Args:
            config_file: Path to the configuration file

        Returns:
            Validated configuration object

        Raises:
            ConfigurationError: If configuration is invalid or missing
        """
        try:
            # Check if config file exists
            config_path = Path(config_file)
            logger.log_info(f"Attempting to load config from: {config_path.absolute()}")
            logger.log_info(f"Config file exists: {config_path.exists()}")

            if not config_path.exists():
                # Try alternative paths
                alt_paths = [
                    Path("config.json"),
                    Path("./config.json"),
                    Path(__file__).parent.parent / "config.json",
                ]
                logger.log_info(
                    f"Trying alternative config paths: {[str(p.absolute()) for p in alt_paths]}"
                )

                for alt_path in alt_paths:
                    if alt_path.exists():
                        logger.log_info(
                            f"Found config at alternative path: {alt_path.absolute()}"
                        )
                        config_path = alt_path
                        break
                else:
                    raise exceptions.ConfigurationError(
                        f"Configuration file not found: {config_file}"
                    )

            # Read and parse config file
            logger.log_info(f"Reading config file: {config_path.absolute()}")
            self._raw_config = self._read_config_file(config_path)

            # Validate and extract configuration
            logger.log_info("Validating and extracting configuration...")
            self.config = self._validate_and_extract_config()

            logger.log_info(
                f"Configuration loaded successfully from {config_path.absolute()}"
            )
            logger.log_info(
                f"Config summary: roms_path={self.config.roms_path}, systems_count={len(self.config.systems_mapping)}"
            )
            return self.config

        except exceptions.ConfigurationError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error loading configuration: {e}"
            logger.log_error(error_msg)
            raise exceptions.ConfigurationError(error_msg)

    def _read_config_file(self, config_path: Path) -> Dict[str, Any]:
        """Read and parse JSON configuration file."""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                file_contents = file.read()
        except (IOError, OSError) as e:
            raise exceptions.ConfigurationError(
                f"Error reading config file {config_path}: {e}"
            )

        try:
            return json.loads(file_contents)
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in config file: {e}"
            logger.log_error(error_msg)
            raise exceptions.ConfigurationError(error_msg)

    def _validate_and_extract_config(self) -> ScraperConfig:
        """Validate and extract configuration values."""
        try:
            # Validate required top-level keys
            required_keys = ["roms", "logos", "colors", "screenscraper"]
            missing_keys = [key for key in required_keys if key not in self._raw_config]
            if missing_keys:
                raise exceptions.ConfigurationError(
                    f"Missing required configuration keys: {missing_keys}"
                )

            # Extract basic configuration
            roms_path = self._raw_config.get("roms")
            systems_logo_path = self._raw_config.get("logos")
            colors = self._raw_config.get("colors", {})

            # Validate screenscraper configuration
            screenscraper_config = self._raw_config.get("screenscraper", {})
            if not screenscraper_config:
                raise exceptions.ConfigurationError(
                    "Missing screenscraper configuration"
                )

            # Extract and validate credentials
            credentials = self._extract_credentials(screenscraper_config)

            # Extract thread configuration
            threads = self._extract_thread_config(screenscraper_config)

            # Extract content configuration
            content = screenscraper_config.get("content", {})
            if not content:
                raise exceptions.ConfigurationError("Missing content configuration")

            show_scraped_roms = screenscraper_config.get("show_scraped_roms", False)

            # Extract and validate content settings
            content_flags = self._extract_content_flags(content)

            # Process systems mapping
            systems_mapping = self._extract_systems_mapping(screenscraper_config)

            return ScraperConfig(
                roms_path=roms_path,
                systems_logo_path=systems_logo_path,
                dev_id=credentials["dev_id"],
                dev_password=credentials["dev_password"],
                username=credentials["username"],
                password=credentials["password"],
                box_enabled=content_flags["box_enabled"],
                preview_enabled=content_flags["preview_enabled"],
                synopsis_enabled=content_flags["synopsis_enabled"],
                show_scraped_roms=show_scraped_roms,
                threads=threads,
                content=content,
                systems_mapping=systems_mapping,
                colors=colors,
            )

        except exceptions.ConfigurationError:
            raise
        except Exception as e:
            raise exceptions.ConfigurationError(f"Error validating configuration: {e}")

    def _extract_credentials(
        self, screenscraper_config: Dict[str, Any]
    ) -> Dict[str, str]:
        """Extract and validate API credentials."""
        dev_id = screenscraper_config.get("devid")
        dev_password = screenscraper_config.get("devpassword")
        username = screenscraper_config.get("username")
        password = screenscraper_config.get("password")

        if not all([dev_id, dev_password, username, password]):
            raise exceptions.ConfigurationError("Missing screenscraper credentials")

        return {
            "dev_id": dev_id,
            "dev_password": dev_password,
            "username": username,
            "password": password,
        }

    def _extract_thread_config(self, screenscraper_config: Dict[str, Any]) -> int:
        """Extract and validate thread configuration."""
        threads_config = screenscraper_config.get("threads", self.DEFAULT_THREAD_COUNT)

        if not isinstance(threads_config, int) or threads_config < 1:
            logger.log_warning(
                f"Invalid thread count {threads_config}, using default: {self.DEFAULT_THREAD_COUNT}"
            )
            return self.DEFAULT_THREAD_COUNT

        return min(threads_config, self.MAX_THREAD_COUNT)

    def _extract_content_flags(self, content: Dict[str, Any]) -> Dict[str, bool]:
        """Extract and validate content feature flags."""
        try:
            return {
                "box_enabled": content["box"]["enabled"],
                "preview_enabled": content["preview"]["enabled"],
                "synopsis_enabled": content["synopsis"]["enabled"],
            }
        except (KeyError, TypeError) as e:
            raise exceptions.ConfigurationError(f"Invalid content configuration: {e}")

    def _extract_systems_mapping(
        self, screenscraper_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract and validate systems mapping."""
        systems_config = screenscraper_config.get("systems", [])
        if not systems_config:
            raise exceptions.ConfigurationError("No systems configured")

        systems_mapping = {}
        for system in systems_config:
            if not isinstance(system, dict) or "dir" not in system:
                logger.log_warning(f"Invalid system configuration: {system}")
                continue
            systems_mapping[system["dir"].lower()] = system

        if not systems_mapping:
            raise exceptions.ConfigurationError(
                "No valid systems found in configuration"
            )

        return systems_mapping

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

        try:
            # Validate roms path
            roms_path = Path(self.config.roms_path)
            if not roms_path.exists():
                raise exceptions.ConfigurationError(
                    f"Roms path does not exist: {self.config.roms_path}"
                )

            if not roms_path.is_dir():
                raise exceptions.ConfigurationError(
                    f"Roms path is not a directory: {self.config.roms_path}"
                )

            if not any(roms_path.iterdir()):
                raise exceptions.ConfigurationError(
                    f"Roms path is empty: {self.config.roms_path}"
                )

            # Validate logos path
            logos_path = Path(self.config.systems_logo_path)
            if not logos_path.exists():
                logger.log_warning(
                    f"Logos path does not exist: {self.config.systems_logo_path}"
                )

            return True

        except exceptions.ConfigurationError:
            raise
        except Exception as e:
            raise exceptions.ConfigurationError(f"Error validating paths: {e}")

    def validate_credentials(self) -> bool:
        """
        Validate API credentials by making a test API call.

        Returns:
            True if credentials are valid, False otherwise

        Raises:
            ConfigurationError: If validation fails due to invalid credentials
        """
        if not self.config:
            raise exceptions.ConfigurationError("Configuration not loaded")

        try:
            # Import here to avoid circular imports
            from scraper import get_user_data

            logger.log_info("Validating API credentials...")

            # Make a test API call to validate credentials
            user_info = get_user_data(
                self.config.dev_id,
                self.config.dev_password,
                self.config.username,
                self.config.password,
            )

            # Check if we got a valid response
            if not user_info or "response" not in user_info:
                logger.log_error("Invalid API response during credential validation")
                raise exceptions.ConfigurationError(
                    "Invalid API credentials - no valid response received"
                )

            # Check for API errors in response
            response = user_info.get("response", {})

            # FIXED: Check for success/error indicators in the response
            has_success = (
                response.get("success") == "true" or response.get("success") is True
            )
            has_error = response.get("error", "") != ""

            # If we have explicit success indicators, treat as successful
            if has_success and not has_error:
                logger.log_info(
                    "Found explicit success indicators in credential validation - proceeding"
                )

                # Check if user info is present
                ssuser = response.get("ssuser", {})
                if not ssuser:
                    logger.log_error("No user information in API response")
                    raise exceptions.ConfigurationError(
                        "Invalid API credentials - no user information returned"
                    )

                # Success path - continue with validation

            elif "erreur" in response:
                error_msg = response["erreur"]
                logger.log_error(
                    f"API credential validation failed with erreur: {error_msg}"
                )
                raise exceptions.ConfigurationError(
                    f"Invalid API credentials: {error_msg}"
                )

            elif has_error:
                error_msg = response.get("error", "Unknown error")
                logger.log_error(
                    f"API credential validation failed with error field: {error_msg}"
                )
                raise exceptions.ConfigurationError(
                    f"Invalid API credentials: {error_msg}"
                )

            else:
                # No explicit success indicators and no explicit errors - check for user info
                ssuser = response.get("ssuser", {})
                if not ssuser:
                    logger.log_error(
                        "No user information in API response and no success indicators"
                    )
                    raise exceptions.ConfigurationError(
                        "Invalid API credentials - no user information returned"
                    )

            # Log successful validation with user info
            username = ssuser.get("nom", "Unknown")
            user_level = ssuser.get("niveau", "Unknown")
            max_threads = ssuser.get("maxthreads", "Unknown")

            logger.log_info(f"API credentials validated successfully")
            logger.log_info(
                f"User: {username}, Level: {user_level}, Max threads: {max_threads}"
            )

            # Validate thread limits against user account
            if isinstance(max_threads, (int, str)) and str(max_threads).isdigit():
                max_threads_int = int(max_threads)
                if self.config.threads > max_threads_int:
                    logger.log_warning(
                        f"Configured threads ({self.config.threads}) exceed user limit ({max_threads_int})"
                    )
                    logger.log_info(
                        f"Adjusting thread count to user limit: {max_threads_int}"
                    )
                    self.config.threads = max_threads_int

            return True

        except exceptions.ForbiddenError as e:
            logger.log_error(f"API access forbidden during credential validation: {e}")
            raise exceptions.ConfigurationError(
                "Invalid API credentials - access forbidden"
            )
        except exceptions.RateLimitError as e:
            logger.log_error(
                f"API rate limit exceeded during credential validation: {e}"
            )
            raise exceptions.ConfigurationError(
                "API rate limit exceeded - please try again later"
            )
        except exceptions.NetworkError as e:
            logger.log_error(f"Network error during credential validation: {e}")
            raise exceptions.ConfigurationError(
                f"Network error validating credentials: {e}"
            )
        except exceptions.ScraperError as e:
            logger.log_error(f"API error during credential validation: {e}")
            raise exceptions.ConfigurationError(f"Invalid API credentials: {e}")
        except Exception as e:
            logger.log_error(f"Unexpected error during credential validation: {e}")
            raise exceptions.ConfigurationError(f"Credential validation failed: {e}")

    def update_systems_from_api(self) -> None:
        """
        Update systems mapping with latest API data.

        This method fetches the latest systems list from ScreenScraper API
        and merges it with the local configuration.
        """
        if not self.config:
            logger.log_warning("Cannot update systems - configuration not loaded")
            return

        try:
            # Import here to avoid circular imports
            from systems_api import (
                build_dynamic_system_mapping,
                get_systems_list,
                merge_system_mappings,
            )

            logger.log_info("Updating systems mapping from ScreenScraper API")

            # Fetch systems from API
            api_systems = get_systems_list(
                self.config.dev_id,
                self.config.dev_password,
                self.config.username,
                self.config.password,
            )

            if api_systems:
                # Build dynamic mapping from API data
                dynamic_mapping = build_dynamic_system_mapping(api_systems)

                if dynamic_mapping:
                    # Merge with existing local configuration
                    merged_mapping = merge_system_mappings(
                        self.config.systems_mapping, dynamic_mapping
                    )

                    # Update configuration
                    self.config.systems_mapping = merged_mapping
                    logger.log_info(
                        f"Successfully updated systems mapping with {len(merged_mapping)} systems"
                    )
                else:
                    logger.log_warning(
                        "Failed to build dynamic system mapping from API data"
                    )
            else:
                logger.log_warning("Failed to fetch systems list from API")

        except exceptions.RateLimitError as e:
            logger.log_warning(f"API rate limit exceeded while updating systems: {e}")
        except exceptions.ForbiddenError as e:
            logger.log_warning(f"API access forbidden while updating systems: {e}")
        except exceptions.NetworkError as e:
            logger.log_warning(f"Network error while updating systems: {e}")
        except Exception as e:
            logger.log_error(f"Unexpected error updating systems from API: {e}")

    def get_system_media_types(self, system_id: str) -> List[str]:
        """
        Get supported media types for a specific system.

        Args:
            system_id: System identifier

        Returns:
            List of supported media types
        """
        if not self.config:
            return []

        # Look for system in current mapping
        for system_key, system_config in self.config.systems_mapping.items():
            if str(system_config.get("id")) == str(system_id):
                # Return supported media from API data if available
                supported_media = system_config.get("supported_media", [])
                if supported_media:
                    return supported_media
                break

        # Fallback to default media types
        return ["box-2D", "box-3D", "mixrbv1", "mixrbv2", "ss", "marquee"]

    def setup_logging(self) -> None:
        """Setup logging based on configuration."""
        log_level_str = self._raw_config.get("log_level", "INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
        logger.setup_logger(log_level)
