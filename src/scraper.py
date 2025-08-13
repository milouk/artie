"""Scraper module with caching and optimized network operations."""

import base64

# hashlib import removed - no longer calculating hashes
import html
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

import exceptions
from cache_manager import api_cached, get_cache_manager
from logger import LoggerSingleton as logger

GAME_INFO_URL = "https://api.screenscraper.fr/api2/jeuInfos.php"
USER_INFO_URL = "https://api.screenscraper.fr/api2/ssuserInfos.php"
MEDIA_DOWNLOAD_URL = "https://api.screenscraper.fr/api2/mediaJeu.php"
VIDEO_DOWNLOAD_URL = "https://api.screenscraper.fr/api2/mediaVideoJeu.php"
MANUAL_DOWNLOAD_URL = "https://api.screenscraper.fr/api2/mediaManuelJeu.php"
MAX_FILE_SIZE_BYTES = 104857600  # 100MB
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VALID_MEDIA_TYPES = {
    # Existing media types
    "box-2D",
    "box-3D",
    "mixrbv1",
    "mixrbv2",
    "ss",
    "marquee",
    # New box variations
    "boitier-texture",
    "boitier-2d",
    "boitier-3d",
    # Support media
    "support-texture",
    "support-2d",
    # Wheel variations
    "wheel",
    "wheelcarbon",
    "wheelsteel",
    # Additional media
    "fanart",
    "video",
    "manuel",
    "flyer",
    # Bezels
    "bezel4-3",
    "bezel16-9",
    "bezel16-10",
    # Screenshots and previews
    "screenshot",
    "titleshot",
    "sstitle",
    # Logos and wheels with regions
    "wheel-hd",
    "wheel-carbon",
    "wheel-steel",
    # Additional box types
    "box-2d-side",
    "box-3d-side",
    "box-texture",
    # Manual variations
    "manuel-fr",
    "manuel-en",
    "manuel-de",
    "manuel-es",
    "manuel-it",
    "manuel-jp",
    # Video variations
    "video-normalized",
    "video-mix",
}


def get_image_files_without_extension(folder: Path) -> List[str]:
    """
    Get image files without extensions from a folder using pathlib.

    Args:
        folder: Path to the folder to scan

    Returns:
        List of filenames without extensions
    """
    folder_path = Path(folder)
    if not folder_path.exists():
        return []

    return [
        f.stem
        for f in folder_path.glob("*")
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]


def get_txt_files_without_extension(folder: Path) -> List[str]:
    """
    Get text files without extensions from a folder using pathlib.

    Args:
        folder: Path to the folder to scan

    Returns:
        List of filenames without extensions
    """
    folder_path = Path(folder)
    if not folder_path.exists():
        return []

    return [f.stem for f in folder_path.glob("*.txt") if f.is_file()]


# Hash calculation functions removed - no longer using hash-based ROM identification


def detect_rom_type(file_path: str) -> str:
    """
    Detect ROM type based on file extension and structure.

    Args:
        file_path: Path to the ROM file

    Returns:
        ROM type: "rom", "iso", or "folder"
    """
    try:
        path = Path(file_path)

        # Check if it's a directory
        if path.is_dir():
            return "folder"

        # Check file extension
        extension = path.suffix.lower()

        # ISO-based formats
        iso_extensions = {
            ".iso",
            ".cue",
            ".bin",
            ".img",
            ".mdf",
            ".nrg",
            ".cdi",
            ".gdi",
        }
        if extension in iso_extensions:
            return "iso"

        # Default to ROM for all other files
        return "rom"

    except Exception as e:
        logger.log_warning(f"Error detecting ROM type for {file_path}: {e}")
        return "rom"  # Default fallback


def get_actual_rom_filename(file_path: str) -> str:
    """
    Get actual ROM filename without modifications.

    Args:
        file_path: Path to the ROM file

    Returns:
        Actual filename without path
    """
    return os.path.basename(file_path)


def validate_rom_parameters(rom_path: str, system_id: str) -> Dict[str, str]:
    """
    Validate and prepare ROM parameters for API call.

    Args:
        rom_path: Path to ROM file
        system_id: System identifier

    Returns:
        Dictionary with validated parameters

    Raises:
        ScraperError: If parameters are invalid
    """
    try:
        # Validate file exists
        if not os.path.exists(rom_path):
            raise exceptions.ScraperError(f"ROM file not found: {rom_path}")

        # Validate system ID format (should be numeric)
        if not system_id or not str(system_id).isdigit():
            raise exceptions.ScraperError(f"Invalid system ID: {system_id}")

        # Detect ROM type
        rom_type = detect_rom_type(rom_path)

        # Get actual filename (no .zip modification)
        rom_filename = get_actual_rom_filename(rom_path)

        # Get file size
        rom_size = str(file_size(rom_path))

        return {"romtype": rom_type, "romnom": rom_filename, "romtaille": rom_size}

    except exceptions.ScraperError:
        raise
    except Exception as e:
        raise exceptions.ScraperError(f"Error validating ROM parameters: {e}")


def clean_rom_name(file_path: str) -> str:
    file_name = os.path.basename(file_path)
    cleaned = re.sub(
        r"(\.nkit|!|&|Disc |Rev |-|\s*\([^()]*\)|\s*\[[^\[\]]*\])",
        " ",
        os.path.splitext(file_name)[0],
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def file_size(file_path: Union[str, Path]) -> int:
    """
    Get file size using pathlib with proper error handling.

    Args:
        file_path: Path to the file

    Returns:
        File size in bytes

    Raises:
        ScraperError: If file cannot be accessed
    """
    try:
        path = Path(file_path)
        return path.stat().st_size
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
        # Validate ROM parameters first
        rom_params = validate_rom_parameters(rom_path, system_id)

        # Hash parameters removed - using filename-based identification only
        params = {
            "devid": base64.b64decode(dev_id).decode(),
            "devpassword": base64.b64decode(dev_password).decode(),
            "softname": "artie",
            "output": "json",
            "ssid": username,
            "sspassword": password,
            "systemeid": system_id,
            "romtype": rom_params["romtype"],
            "romnom": rom_params["romnom"],
            "romtaille": rom_params["romtaille"],
        }
        return urlunparse(urlparse(GAME_INFO_URL)._replace(query=urlencode(params)))
    except (UnicodeDecodeError, exceptions.ScraperError) as e:
        raise exceptions.ScraperError(f"Error encoding URL: {e}")


def parse_user_info_url(
    dev_id: str, dev_password: str, username: str, password: str
) -> str:
    try:
        params = {
            "devid": base64.b64decode(dev_id).decode(),
            "devpassword": base64.b64decode(dev_password).decode(),
            "softname": "artie",
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


def check_destination(dest: Union[str, Path]) -> None:
    """
    Ensure destination directory exists using pathlib.

    Args:
        dest: Destination file path

    Raises:
        ScraperError: If directory cannot be created
    """
    try:
        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise exceptions.ScraperError(
            f"Error creating directory {dest_path.parent}: {e}"
        )


def get(url: str, max_retries: int = 3, timeout: int = 30) -> bytes:
    """
    Fetch data from URL with optimized connection pooling and retry logic.

    This function uses persistent HTTP sessions with connection pooling for
    better performance, especially when making multiple requests to the same domain.

    Args:
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds

    Returns:
        Response content as bytes

    Raises:
        ForbiddenError: For 403 status codes
        RateLimitError: For 430 status codes
        NetworkError: For network-related errors
        ScraperError: For other HTTP errors
    """
    import time

    # Check if we recently hit 403 errors to avoid hammering the API
    cache_manager = get_cache_manager()
    forbidden_key = "forbidden_error_cache"

    if cache_manager.get(forbidden_key, "memory"):
        logger.log_warning("Skipping request due to recent 403 Forbidden error")
        raise exceptions.ForbiddenError(
            "Recent 403 Forbidden error - avoiding additional requests"
        )

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            # PERFORMANCE OPTIMIZATION: Use optimized session with connection pooling
            session = _get_optimized_session()

            response = session.get(url, timeout=timeout)
            response.raise_for_status()

            # Validate response content
            if not response.content:
                raise exceptions.NetworkError("Empty response received")

            return response.content

        except requests.Timeout as e:
            last_exception = exceptions.NetworkError(
                f"Request timed out after {timeout}s: {e}"
            )

        except requests.HTTPError as e:
            status = e.response.status_code if e.response else 0
            response_text = ""

            # Try to get response text for better error messages
            try:
                if e.response and e.response.content:
                    response_text = e.response.content.decode("utf-8", errors="ignore")[
                        :200
                    ]
            except Exception:
                pass

            if status == 400:
                error_msg = "Bad request - malformed URL or invalid parameters"
                if response_text:
                    error_msg += f". Response: {response_text}"
                logger.log_error(f"400 Bad Request error: {error_msg}")
                raise exceptions.BadRequestError(error_msg)

            elif status == 401:
                error_msg = "API closed for non-members or inactive members"
                if response_text:
                    error_msg += f". Response: {response_text}"
                logger.log_error(f"401 API Closed error: {error_msg}")
                raise exceptions.APIClosedError(error_msg)

            elif status == 403:
                # Cache 403 errors for 5 minutes to avoid hammering the API
                cache_manager.set(forbidden_key, True, ttl=300, cache_type="memory")

                error_msg = (
                    "Forbidden request - invalid credentials or insufficient privileges"
                )
                if response_text:
                    error_msg += f". Response: {response_text}"

                logger.log_error(f"403 Forbidden error: {error_msg}")
                raise exceptions.ForbiddenError(error_msg)

            elif status == 404:
                raise exceptions.ScraperError(f"Resource not found: {url}")

            elif status == 423:
                error_msg = "API fully closed due to server problems"
                if response_text:
                    error_msg += f". Response: {response_text}"
                logger.log_error(f"423 API Fully Closed error: {error_msg}")
                raise exceptions.APIFullyClosedError(error_msg)

            elif status == 426:
                error_msg = "Software blacklisted or obsolete version"
                if response_text:
                    error_msg += f". Response: {response_text}"
                logger.log_error(f"426 Software Blacklisted error: {error_msg}")
                raise exceptions.SoftwareBlacklistedError(error_msg)

            elif status == 429:
                # Enhanced 429 handling with different thread limit types
                error_msg = "Thread limit exceeded"
                if response_text:
                    error_msg += f". Response: {response_text}"

                    # Determine specific thread limit type
                    response_lower = response_text.lower()
                    if "member thread limit" in response_lower:
                        error_msg = "Member thread limit reached"
                    elif "threads per minute" in response_lower:
                        error_msg = "Threads per minute exceeded"
                    elif "maximum listening threads" in response_lower:
                        error_msg = "Maximum listening threads exceeded"
                    elif "maximum total threads" in response_lower:
                        error_msg = "Maximum total threads exceeded"

                logger.log_error(f"429 Thread Limit error: {error_msg}")
                raise exceptions.ThreadLimitError(error_msg)

            elif status == 430:
                # Enhanced rate limit handling with exponential backoff
                error_msg = "Rate limit exceeded - reduce thread count or wait longer"
                if response_text:
                    error_msg += f". Response: {response_text}"

                logger.log_error(f"430 Rate limit error: {error_msg}")
                raise exceptions.RateLimitError(error_msg)

            elif status == 431:
                error_msg = "Too many unrecognized ROMs scraped"
                if response_text:
                    error_msg += f". Response: {response_text}"
                logger.log_error(f"431 Too Many Unrecognized error: {error_msg}")
                raise exceptions.TooManyUnrecognizedError(error_msg)

            elif status >= 500:
                # Server errors might be temporary, allow retry
                last_exception = exceptions.NetworkError(f"Server error {status}: {e}")

            else:
                # Client errors are usually permanent
                error_msg = f"HTTP error {status}: {e}"
                if response_text:
                    error_msg += f". Response: {response_text}"
                raise exceptions.ScraperError(error_msg)

        except requests.ConnectionError as e:
            last_exception = exceptions.NetworkError(f"Connection error: {e}")

        except requests.RequestException as e:
            last_exception = exceptions.NetworkError(f"Request failed: {e}")

        except Exception as e:
            # Catch any unexpected errors
            last_exception = exceptions.ScraperError(
                f"Unexpected error fetching {url}: {e}"
            )

        # If we get here, we had a retryable error
        if attempt < max_retries:
            wait_time = min(2**attempt, 10)  # Exponential backoff, max 10s
            logger.log_warning(
                f"Request failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {wait_time}s: {last_exception}"
            )
            time.sleep(wait_time)
        else:
            logger.log_error(
                f"Request failed after {max_retries + 1} attempts: {last_exception}"
            )

    # If we exhausted all retries, raise the last exception
    if last_exception:
        raise last_exception
    else:
        raise exceptions.NetworkError(
            f"Failed to fetch {url} after {max_retries + 1} attempts"
        )


def fetch_data(url: str) -> Any:
    """
    Fetch and parse JSON data from URL with comprehensive error handling.

    Args:
        url: URL to fetch JSON data from

    Returns:
        Parsed JSON data

    Raises:
        ScraperError: For various parsing and API errors
        NetworkError: For network-related issues
    """
    try:
        body = get(url)

        # Decode response with proper error handling
        try:
            body_str = body.decode("utf-8")
        except UnicodeDecodeError as e:
            # Try with different encodings
            try:
                body_str = body.decode("latin-1")
                logger.log_warning(f"Used latin-1 encoding for response from {url}")
            except UnicodeDecodeError:
                raise exceptions.ScraperError(
                    f"Unable to decode response from {url}: {e}"
                )

        if not body_str.strip():
            raise exceptions.ScraperError("Empty response body")

        # FIXED: Check for explicit success indicators first to avoid false positives
        has_success_true = (
            '"success": "true"' in body_str or '"success":true' in body_str
        )
        has_empty_error = '"error": ""' in body_str or '"error":""' in body_str

        # If we have clear success indicators, skip error detection
        if has_success_true and has_empty_error:
            logger.log_info(
                "Found explicit success indicators, skipping error detection"
            )
        else:
            # Check for API error messages with precise quota detection
            error_indicators = ["API closed", "Erreur", "Error", "erreur"]
            # More specific quota exceeded indicators to avoid false positives
            quota_exceeded_indicators = [
                "quota exceeded",
                "quota dépassé",
                "limite dépassée",
                "limit exceeded",
                "trop de requêtes",
                "too many requests",
                "rate limit exceeded",
                "quota atteint",
                "limite atteinte",
            ]

            if any(err.lower() in body_str.lower() for err in error_indicators):
                logger.log_warning(f"API error detected in response: {body_str[:300]}")

                # Precise quota detection - only trigger on explicit quota exceeded messages
                quota_matches = [
                    ind
                    for ind in quota_exceeded_indicators
                    if ind.lower() in body_str.lower()
                ]
                if quota_matches:
                    logger.log_error(f"API quota exceeded detected: {body_str}")
                    raise exceptions.RateLimitError(f"API quota exceeded: {body_str}")
                elif "forbidden" in body_str.lower():
                    logger.log_error(f"API access forbidden: {body_str[:300]}")
                    raise exceptions.ForbiddenError(f"API access forbidden: {body_str}")
                else:
                    logger.log_error(f"Generic API error: {body_str[:300]}")
                    raise exceptions.ScraperError(f"API error in response: {body_str}")

        # Parse JSON with detailed error reporting
        try:
            data = json.loads(body_str)

            # Validate response structure for ScreenScraper API
            if isinstance(data, dict):
                # FIXED: Check for explicit success indicators in structured response first
                response = data.get("response", {})
                has_success = (
                    response.get("success") == "true" or response.get("success") is True
                )
                has_empty_error = response.get("error", "") == ""

                # If we have explicit success indicators, treat as successful regardless of other content
                if has_success and has_empty_error:
                    logger.log_info(
                        "Found explicit success indicators in structured response, treating as successful"
                    )
                    return data

                # Check for API-specific error responses only if no success indicators
                if "erreur" in data:
                    error_msg = data["erreur"]
                    logger.log_error(f"API returned structured error: {error_msg}")

                    # Check if the structured error indicates quota issues - use precise indicators
                    quota_matches_structured = [
                        ind
                        for ind in quota_exceeded_indicators
                        if ind.lower() in str(error_msg).lower()
                    ]
                    if quota_matches_structured:
                        raise exceptions.RateLimitError(
                            f"API quota exceeded (structured): {error_msg}"
                        )
                    else:
                        raise exceptions.ScraperError(
                            f"API returned error: {error_msg}"
                        )

                # Check for explicit error indicators in response
                elif response.get("error") and response.get("error") != "":
                    error_msg = response.get("error")
                    logger.log_error(f"API returned response error: {error_msg}")
                    raise exceptions.ScraperError(f"API returned error: {error_msg}")

                elif (
                    data.get("header", {}).get("APIversion") is None
                    and "response" not in data
                ):
                    logger.log_warning(
                        f"Unexpected response structure from {url}: {list(data.keys())}"
                    )

            return data

        except json.JSONDecodeError as e:
            raise exceptions.ScraperError(f"Invalid JSON response from {url}: {e}")

    except exceptions.ScraperError:
        # Re-raise scraper errors
        raise
    except Exception as e:
        # Catch any unexpected errors
        raise exceptions.ScraperError(f"Unexpected error fetching data from {url}: {e}")


@api_cached(ttl=3600)  # Cache game data for 1 hour
def get_game_data(
    system_id: str,
    rom_path: str,
    dev_id: str,
    dev_password: str,
    username: str,
    password: str,
    enable_fallback: bool = True,
) -> Any:
    """
    Get game data from ScreenScraper API with caching, quota awareness, and fallback search.

    Args:
        system_id: System identifier
        rom_path: Path to ROM file
        dev_id: Developer ID (base64 encoded)
        dev_password: Developer password (base64 encoded)
        username: Username
        password: Password
        enable_fallback: Whether to use fallback search if hash lookup fails

    Returns:
        Game data from API

    Raises:
        RateLimitError: When API quota is exceeded
        ForbiddenError: When API access is forbidden
        ScraperError: For other API errors
    """
    # Check if we recently hit quota limits
    cache_manager = get_cache_manager()
    quota_key = f"quota_exceeded_{username}"

    cached_quota_state = cache_manager.get(quota_key, "memory")
    if cached_quota_state:
        logger.log_warning("Skipping API call due to recent quota exceeded error")
        raise exceptions.RateLimitError(
            "API quota recently exceeded, avoiding additional calls"
        )

    try:
        # Primary filename-based lookup (hash functionality removed)
        game_url = parse_find_game_url(
            system_id, rom_path, dev_id, dev_password, username, password
        )
        game_data = fetch_data(game_url)

        # Check if we got valid game data
        if game_data and isinstance(game_data, dict):
            response = game_data.get("response", {})
            if "jeu" in response and response["jeu"]:
                logger.log_info(
                    f"ROM lookup successful for {os.path.basename(rom_path)}"
                )
                return game_data

        # If ROM lookup didn't return valid data and fallback is enabled, try name search
        if enable_fallback:
            logger.log_info(
                f"ROM lookup failed for {os.path.basename(rom_path)}, trying fallback search"
            )

            # Import here to avoid circular imports
            from search_api import search_game_by_name

            # Extract game name from ROM path
            rom_name = clean_rom_name(rom_path)

            try:
                search_result = search_game_by_name(
                    rom_name, system_id, dev_id, dev_password, username, password
                )

                if search_result:
                    # Convert search result to same format as hash lookup
                    fallback_data = {
                        "header": game_data.get("header", {}) if game_data else {},
                        "response": {"jeu": search_result},
                    }
                    logger.log_info(f"Fallback search successful for {rom_name}")
                    return fallback_data
                else:
                    logger.log_info(f"Fallback search found no results for {rom_name}")

            except (exceptions.RateLimitError, exceptions.ForbiddenError):
                # Re-raise quota/auth errors from fallback search
                raise
            except Exception as e:
                logger.log_warning(f"Fallback search failed for {rom_name}: {e}")
                # Continue to return original result even if fallback fails

        # Return original result (may be empty/invalid)
        return game_data

    except exceptions.RateLimitError as e:
        # Cache quota exceeded state for 10 minutes to avoid hammering the API
        cache_manager.set(quota_key, True, ttl=600, cache_type="memory")
        logger.log_error(f"API quota exceeded, caching error state: {e}")
        raise


@api_cached(ttl=300)  # Cache user data for 5 minutes
def get_user_data(dev_id: str, dev_password: str, username: str, password: str) -> Any:
    """
    Get user data from ScreenScraper API with caching.

    Args:
        dev_id: Developer ID (base64 encoded)
        dev_password: Developer password (base64 encoded)
        username: Username
        password: Password

    Returns:
        User data from API
    """
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
    """
    Fetch box art for a game.

    Args:
        game: Game data from API
        config: Configuration for box art

    Returns:
        Box art image data or None

    Raises:
        ScraperError: If download fails
    """
    try:
        medias = game["response"]["jeu"]["medias"]
        regions = config.get("regions", ["us", "ame", "wor"])
        return _fetch_media(medias, config["box"], regions)
    except exceptions.ScraperError as e:
        raise exceptions.ScraperError(f"Error downloading box: {e}")


def fetch_preview(game: dict, config: dict) -> Optional[bytes]:
    """
    Fetch preview image for a game.

    Args:
        game: Game data from API
        config: Configuration for preview

    Returns:
        Preview image data or None

    Raises:
        ScraperError: If download fails
    """
    try:
        medias = game["response"]["jeu"]["medias"]
        regions = config.get("regions", ["us", "ame", "wor"])
        return _fetch_media(medias, config["preview"], regions)
    except exceptions.ScraperError as e:
        raise exceptions.ScraperError(f"Error downloading preview: {e}")


def fetch_synopsis(game: dict, config: dict) -> Optional[str]:
    """
    Fetch synopsis text for a game.

    Args:
        game: Game data from API
        config: Configuration for synopsis

    Returns:
        Synopsis text or None
    """
    synopsis = game["response"]["jeu"].get("synopsis")
    if not synopsis:
        return None

    synopsis_lang = config["synopsis"]["lang"]
    synopsis_text = next(
        (item["text"] for item in synopsis if item.get("langue") == synopsis_lang), None
    )
    return html.unescape(synopsis_text) if synopsis_text else None


def clear_rate_limit_cache(username: str) -> bool:
    """
    Clear cached rate limit state for a user.

    Args:
        username: Username to clear cache for

    Returns:
        True if cache was cleared, False if no cache existed
    """
    cache_manager = get_cache_manager()
    quota_key = f"quota_exceeded_{username}"

    cached_state = cache_manager.get(quota_key, "memory")
    if cached_state:
        cache_manager.delete(quota_key, "memory")
        logger.log_info(f"Cleared cached quota exceeded state for user '{username}'")
        return True
    else:
        return False


def check_rate_limit_cache_status(username: str) -> dict:
    """
    Check the current rate limit cache status for a user.

    Args:
        username: Username to check

    Returns:
        Dictionary with cache status information
    """
    cache_manager = get_cache_manager()
    quota_key = f"quota_exceeded_{username}"
    forbidden_key = "forbidden_error_cache"

    quota_cached = cache_manager.get(quota_key, "memory")
    forbidden_cached = cache_manager.get(forbidden_key, "memory")

    status = {
        "quota_exceeded_cached": bool(quota_cached),
        "quota_cache_value": quota_cached,
        "forbidden_error_cached": bool(forbidden_cached),
        "forbidden_cache_value": forbidden_cached,
        "quota_cache_key": quota_key,
        "forbidden_cache_key": forbidden_key,
    }

    return status


def parse_media_download_url(
    game_id: str,
    media_type: str,
    dev_id: str,
    dev_password: str,
    username: str,
    password: str,
    **kwargs,
) -> str:
    """
    Build direct media download URL.

    Args:
        game_id: Game identifier
        media_type: Type of media to download
        dev_id: Developer ID (base64 encoded)
        dev_password: Developer password (base64 encoded)
        username: Username
        password: Password
        **kwargs: Additional parameters (maxwidth, maxheight, outputformat, etc.)

    Returns:
        Complete media download URL

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
            "gameid": game_id,
            "media": media_type,
        }

        # Add optional parameters for media optimization
        for key, value in kwargs.items():
            if value is not None:
                params[key] = str(value)

        return urlunparse(
            urlparse(MEDIA_DOWNLOAD_URL)._replace(query=urlencode(params))
        )

    except (UnicodeDecodeError, Exception) as e:
        raise exceptions.ScraperError(f"Error encoding media download URL: {e}")


def download_media_direct(
    game_id: str,
    media_type: str,
    dev_id: str,
    dev_password: str,
    username: str,
    password: str,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    output_format: Optional[str] = None,
    **kwargs,
) -> Optional[bytes]:
    """
    Download media using direct media endpoints with optimization features.

    Args:
        game_id: Game identifier
        media_type: Type of media to download
        dev_id: Developer ID (base64 encoded)
        dev_password: Developer password (base64 encoded)
        username: Username
        password: Password
        max_width: Maximum width for server-side resizing
        max_height: Maximum height for server-side resizing
        output_format: Output format (png, jpg)
        **kwargs: Additional parameters

    Returns:
        Media data as bytes or None if not found

    Raises:
        RateLimitError: When API quota is exceeded
        ForbiddenError: When API access is forbidden
        ScraperError: For other API errors
    """
    try:
        # Validate media type
        is_media_type_valid(media_type)

        # Build parameters for optimization
        params = {}
        if max_width:
            params["maxwidth"] = max_width
        if max_height:
            params["maxheight"] = max_height
        if output_format:
            params["outputformat"] = output_format

        # Add any additional parameters
        params.update(kwargs)

        logger.log_info(
            f"Downloading media directly: game_id={game_id}, type={media_type}"
        )

        media_url = parse_media_download_url(
            game_id, media_type, dev_id, dev_password, username, password, **params
        )

        return get(media_url)

    except exceptions.ScraperError as e:
        if "not found" in str(e).lower():
            logger.log_info(f"Media not found: game_id={game_id}, type={media_type}")
            return None
        raise
    except (exceptions.RateLimitError, exceptions.ForbiddenError):
        # Re-raise API errors
        raise
    except Exception as e:
        logger.log_error(f"Unexpected error downloading media: {e}")
        raise exceptions.ScraperError(f"Media download failed: {e}")


def download_video_direct(
    game_id: str, dev_id: str, dev_password: str, username: str, password: str, **kwargs
) -> Optional[bytes]:
    """
    Download video using direct video endpoint.

    Args:
        game_id: Game identifier
        dev_id: Developer ID (base64 encoded)
        dev_password: Developer password (base64 encoded)
        username: Username
        password: Password
        **kwargs: Additional parameters

    Returns:
        Video data as bytes or None if not found
    """
    try:
        params = {
            "devid": base64.b64decode(dev_id).decode(),
            "devpassword": base64.b64decode(dev_password).decode(),
            "softname": "artie",
            "output": "json",
            "ssid": username,
            "sspassword": password,
            "gameid": game_id,
        }

        # Add additional parameters
        params.update(kwargs)

        logger.log_info(f"Downloading video directly: game_id={game_id}")

        video_url = urlunparse(
            urlparse(VIDEO_DOWNLOAD_URL)._replace(query=urlencode(params))
        )
        return get(video_url)

    except exceptions.ScraperError as e:
        if "not found" in str(e).lower():
            logger.log_info(f"Video not found: game_id={game_id}")
            return None
        raise
    except Exception as e:
        logger.log_error(f"Error downloading video: {e}")
        raise exceptions.ScraperError(f"Video download failed: {e}")


def download_manual_direct(
    game_id: str,
    dev_id: str,
    dev_password: str,
    username: str,
    password: str,
    language: Optional[str] = None,
    **kwargs,
) -> Optional[bytes]:
    """
    Download manual using direct manual endpoint.

    Args:
        game_id: Game identifier
        dev_id: Developer ID (base64 encoded)
        dev_password: Developer password (base64 encoded)
        username: Username
        password: Password
        language: Manual language (fr, en, de, etc.)
        **kwargs: Additional parameters

    Returns:
        Manual data as bytes or None if not found
    """
    try:
        params = {
            "devid": base64.b64decode(dev_id).decode(),
            "devpassword": base64.b64decode(dev_password).decode(),
            "softname": "artie",
            "output": "json",
            "ssid": username,
            "sspassword": password,
            "gameid": game_id,
        }

        if language:
            params["langue"] = language

        # Add additional parameters
        params.update(kwargs)

        logger.log_info(
            f"Downloading manual directly: game_id={game_id}, language={language}"
        )

        manual_url = urlunparse(
            urlparse(MANUAL_DOWNLOAD_URL)._replace(query=urlencode(params))
        )
        return get(manual_url)

    except exceptions.ScraperError as e:
        if "not found" in str(e).lower():
            logger.log_info(f"Manual not found: game_id={game_id}, language={language}")
            return None
        raise
    except Exception as e:
        logger.log_error(f"Error downloading manual: {e}")
        raise exceptions.ScraperError(f"Manual download failed: {e}")


# Global session for connection pooling optimization
_global_session = None
_session_lock = None


def _get_optimized_session():
    """
    Get or create an optimized HTTP session with connection pooling.

    This provides significant performance improvements by reusing connections
    and implementing proper connection pooling for multiple requests.
    """
    global _global_session, _session_lock

    if _session_lock is None:
        import threading

        _session_lock = threading.Lock()

    with _session_lock:
        if _global_session is None:
            import requests.adapters
            from urllib3.util.retry import Retry

            _global_session = requests.Session()

            # Configure connection pooling for better performance
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=20,  # Increased from 10
                pool_maxsize=50,  # Increased from 20
                max_retries=0,  # We handle retries ourselves
                pool_block=False,  # Don't block when pool is full
            )

            _global_session.mount("http://", adapter)
            _global_session.mount("https://", adapter)

            # Set optimized headers
            _global_session.headers.update(
                {
                    "User-Agent": "artie-scraper/2.0 (optimized)",
                    "Connection": "keep-alive",
                    "Accept-Encoding": "gzip, deflate",
                }
            )

            logger.log_info(
                "PERFORMANCE: Initialized optimized HTTP session with connection pooling"
            )

    return _global_session


def cleanup_network_resources():
    """Clean up network resources on application shutdown."""
    global _global_session
    if _global_session:
        _global_session.close()
        _global_session = None
        logger.log_info("PERFORMANCE: Cleaned up HTTP session resources")
        logger.log_info("PERFORMANCE: Cleaned up HTTP session resources")
