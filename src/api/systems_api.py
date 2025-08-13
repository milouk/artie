"""Systems API module for ScreenScraper dynamic system discovery."""

import base64
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse, urlunparse

import exceptions
from cache_manager import api_cached
from logger import LoggerSingleton as logger
from scraper import fetch_data

SYSTEMS_LIST_URL = "https://api.screenscraper.fr/api2/systemesListe.php"


def parse_systems_list_url(
    dev_id: str, dev_password: str, username: str, password: str, **kwargs
) -> str:
    """
    Build systems list API URL.

    Args:
        dev_id: Developer ID (base64 encoded)
        dev_password: Developer password (base64 encoded)
        username: Username
        password: Password
        **kwargs: Additional parameters (frontend, etc.)

    Returns:
        Complete systems list URL

    Raises:
        ScraperError: If URL encoding fails
    """
    try:
        params = {
            "devid": base64.b64decode(dev_id).decode(),
            "devpassword": base64.b64decode(dev_password).decode(),
            "softname": "artie",
            "output": "json",
            "ssid": username,
            "sspassword": password,
        }

        # Add optional parameters
        for key, value in kwargs.items():
            if value is not None:
                params[key] = str(value)

        return urlunparse(urlparse(SYSTEMS_LIST_URL)._replace(query=urlencode(params)))

    except (UnicodeDecodeError, Exception) as e:
        raise exceptions.ScraperError(f"Error encoding systems list URL: {e}")


@api_cached(ttl=86400)  # Cache systems list for 24 hours
def get_systems_list(
    dev_id: str,
    dev_password: str,
    username: str,
    password: str,
    frontend: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive systems list from ScreenScraper API.

    Args:
        dev_id: Developer ID (base64 encoded)
        dev_password: Developer password (base64 encoded)
        username: Username
        password: Password
        frontend: Frontend type (recalbox, retropie, etc.)

    Returns:
        Systems data from API or None if failed

    Raises:
        RateLimitError: When API quota is exceeded
        ForbiddenError: When API access is forbidden
        ScraperError: For other API errors
    """
    try:
        logger.log_info("Fetching systems list from ScreenScraper API")

        systems_url = parse_systems_list_url(
            dev_id, dev_password, username, password, frontend=frontend
        )

        systems_data = fetch_data(systems_url)

        if not systems_data:
            logger.log_warning("No systems data received from API")
            return None

        # Validate response structure
        if isinstance(systems_data, dict) and "response" in systems_data:
            systems = systems_data["response"].get("systemes", [])
            logger.log_info(f"Retrieved {len(systems)} systems from API")
            return systems_data
        else:
            logger.log_warning("Unexpected systems API response structure")
            return None

    except (
        exceptions.RateLimitError,
        exceptions.ForbiddenError,
        exceptions.ScraperError,
    ):
        # Re-raise API errors
        raise
    except Exception as e:
        logger.log_error(f"Unexpected error fetching systems list: {e}")
        raise exceptions.ScraperError(f"Systems list fetch failed: {e}")


def build_dynamic_system_mapping(api_systems: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build system mapping from API response.

    Args:
        api_systems: Systems data from API

    Returns:
        Dictionary mapping system directories to system configurations
    """
    try:
        if not api_systems or "response" not in api_systems:
            logger.log_warning("Invalid systems data for mapping")
            return {}

        systems = api_systems["response"].get("systemes", [])
        if not systems:
            logger.log_warning("No systems found in API response")
            return {}

        system_mapping = {}

        for system in systems:
            try:
                # Extract system information
                system_id = system.get("id")
                system_name = system.get("nom", "")
                system_names = system.get("noms", [])

                if not system_id:
                    continue

                # Get directory names from various sources
                directory_names = set()

                # Add main system name
                if system_name:
                    directory_names.add(system_name.lower())

                # Add alternative names
                for name_entry in system_names:
                    if isinstance(name_entry, dict):
                        name_text = name_entry.get("text", "")
                        if name_text:
                            directory_names.add(name_text.lower())
                    elif isinstance(name_entry, str):
                        directory_names.add(name_entry.lower())

                # Get supported media types
                supported_media = []
                medias = system.get("medias", [])
                for media in medias:
                    media_type = media.get("type")
                    if media_type:
                        supported_media.append(media_type)

                # Create system configuration for each directory name
                for dir_name in directory_names:
                    if dir_name and dir_name not in system_mapping:
                        system_mapping[dir_name] = {
                            "id": system_id,
                            "name": system_name,
                            "dir": dir_name,
                            "supported_media": supported_media,
                            "api_data": system,  # Store full API data for reference
                        }

            except Exception as e:
                logger.log_warning(
                    f"Error processing system {system.get('id', 'unknown')}: {e}"
                )
                continue

        logger.log_info(
            f"Built dynamic system mapping with {len(system_mapping)} entries"
        )
        return system_mapping

    except Exception as e:
        logger.log_error(f"Error building dynamic system mapping: {e}")
        return {}


def merge_system_mappings(
    local_mapping: Dict[str, Any], dynamic_mapping: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge local system mapping with dynamic API mapping.

    Args:
        local_mapping: Local system configuration
        dynamic_mapping: Dynamic mapping from API

    Returns:
        Merged system mapping with local config taking precedence
    """
    try:
        merged_mapping = {}

        # Start with dynamic mapping as base
        for system_key, system_config in dynamic_mapping.items():
            merged_mapping[system_key] = system_config.copy()

        # Override with local configuration
        for system_key, local_config in local_mapping.items():
            system_key_lower = system_key.lower()

            if system_key_lower in merged_mapping:
                # Merge configurations, local takes precedence
                merged_config = merged_mapping[system_key_lower].copy()
                merged_config.update(local_config)
                merged_mapping[system_key_lower] = merged_config
            else:
                # Add local-only system
                merged_mapping[system_key_lower] = local_config.copy()

        logger.log_info(f"Merged system mappings: {len(merged_mapping)} total systems")
        return merged_mapping

    except Exception as e:
        logger.log_error(f"Error merging system mappings: {e}")
        # Return local mapping as fallback
        return local_mapping


def get_system_media_types(system_id: str, systems_data: Dict[str, Any]) -> List[str]:
    """
    Get supported media types for a specific system.

    Args:
        system_id: System identifier
        systems_data: Systems data from API

    Returns:
        List of supported media types
    """
    try:
        if not systems_data or "response" not in systems_data:
            return []

        systems = systems_data["response"].get("systemes", [])

        for system in systems:
            if str(system.get("id")) == str(system_id):
                medias = system.get("medias", [])
                return [media.get("type") for media in medias if media.get("type")]

        return []

    except Exception as e:
        logger.log_warning(f"Error getting media types for system {system_id}: {e}")
        return []


def validate_system_configuration(system_config: Dict[str, Any]) -> bool:
    """
    Validate system configuration has required fields.

    Args:
        system_config: System configuration to validate

    Returns:
        True if valid, False otherwise
    """
    required_fields = ["id", "dir"]

    try:
        for field in required_fields:
            if field not in system_config or not system_config[field]:
                logger.log_warning(
                    f"System configuration missing required field: {field}"
                )
                return False

        # Validate system ID is numeric
        system_id = system_config["id"]
        if not str(system_id).isdigit():
            logger.log_warning(f"Invalid system ID format: {system_id}")
            return False

        return True

    except Exception as e:
        logger.log_warning(f"Error validating system configuration: {e}")
        return False
