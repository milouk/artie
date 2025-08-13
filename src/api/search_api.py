"""Search API module for ScreenScraper fallback search functionality."""

import base64
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlparse, urlunparse

import exceptions
from cache_manager import api_cached
from logger import LoggerSingleton as logger
from scraper import fetch_data

SEARCH_URL = "https://api.screenscraper.fr/api2/jeuRecherche.php"


def parse_search_url(
    search_term: str,
    system_id: str,
    dev_id: str,
    dev_password: str,
    username: str,
    password: str,
    **kwargs,
) -> str:
    """
    Build search API URL for name-based game search.

    Args:
        search_term: Game name to search for
        system_id: System identifier
        dev_id: Developer ID (base64 encoded)
        dev_password: Developer password (base64 encoded)
        username: Username
        password: Password
        **kwargs: Additional search parameters

    Returns:
        Complete search URL

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
            "recherche": search_term,
            "systemeid": system_id,
        }

        # Add optional parameters
        for key, value in kwargs.items():
            if value is not None:
                params[key] = str(value)

        return urlunparse(urlparse(SEARCH_URL)._replace(query=urlencode(params)))

    except (UnicodeDecodeError, Exception) as e:
        raise exceptions.ScraperError(f"Error encoding search URL: {e}")


@api_cached(ttl=1800)  # Cache search results for 30 minutes
def search_game_by_name(
    game_name: str,
    system_id: str,
    dev_id: str,
    dev_password: str,
    username: str,
    password: str,
    **kwargs,
) -> Optional[Any]:
    """
    Search for game by name when ROM lookup fails.

    Args:
        game_name: Game name to search for
        system_id: System identifier
        dev_id: Developer ID (base64 encoded)
        dev_password: Developer password (base64 encoded)
        username: Username
        password: Password
        **kwargs: Additional search parameters (region, langue, etc.)

    Returns:
        Game data from API or None if not found

    Raises:
        RateLimitError: When API quota is exceeded
        ForbiddenError: When API access is forbidden
        ScraperError: For other API errors
    """
    try:
        # Clean the game name for better search results
        cleaned_name = clean_search_term(game_name)

        logger.log_info(
            f"Searching for game by name: '{cleaned_name}' on system {system_id}"
        )

        search_url = parse_search_url(
            cleaned_name, system_id, dev_id, dev_password, username, password, **kwargs
        )

        search_results = fetch_data(search_url)

        if not search_results:
            logger.log_info(f"No search results found for '{cleaned_name}'")
            return None

        # Process search results to find best match
        best_match = find_best_search_match(search_results, cleaned_name)

        if best_match:
            logger.log_info(
                f"Found search match for '{cleaned_name}': {best_match.get('nom', 'Unknown')}"
            )
            return best_match
        else:
            logger.log_info(
                f"No suitable match found in search results for '{cleaned_name}'"
            )
            return None

    except (
        exceptions.RateLimitError,
        exceptions.ForbiddenError,
        exceptions.ScraperError,
    ):
        # Re-raise API errors
        raise
    except Exception as e:
        logger.log_error(f"Unexpected error in name search for '{game_name}': {e}")
        raise exceptions.ScraperError(f"Search failed: {e}")


def clean_search_term(game_name: str) -> str:
    """
    Clean game name for better search results.

    Args:
        game_name: Original game name

    Returns:
        Cleaned search term
    """
    import re

    # Remove common ROM naming patterns
    cleaned = re.sub(
        r"(\.nkit|!|&|Disc\s+\d+|Rev\s+\w+|\s*\([^()]*\)|\s*\[[^\[\]]*\])",
        " ",
        game_name,
        flags=re.IGNORECASE,
    )

    # Remove file extensions
    cleaned = re.sub(
        r"\.(zip|rar|7z|gz|rom|iso|bin|cue|img)$", "", cleaned, flags=re.IGNORECASE
    )

    # Clean up whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Remove leading/trailing punctuation
    cleaned = cleaned.strip(".-_")

    return cleaned


def find_best_search_match(
    search_results: Any, search_term: str
) -> Optional[Dict[str, Any]]:
    """
    Find the best match from search results.

    Args:
        search_results: API search response
        search_term: Original search term

    Returns:
        Best matching game data or None
    """
    try:
        # Handle different response structures
        if isinstance(search_results, dict):
            if "response" in search_results:
                games = search_results["response"].get("jeux", [])
            elif "jeux" in search_results:
                games = search_results["jeux"]
            else:
                return None
        else:
            return None

        if not games:
            return None

        # If only one result, return it
        if len(games) == 1:
            return games[0]

        # Find best match based on name similarity
        best_match = None
        best_score = 0

        search_lower = search_term.lower()

        for game in games:
            game_name = game.get("nom", "").lower()

            # Calculate simple similarity score
            score = calculate_name_similarity(search_lower, game_name)

            if score > best_score:
                best_score = score
                best_match = game

        # Only return match if similarity is reasonable
        if best_score > 0.5:  # 50% similarity threshold
            return best_match

        # If no good match, return the first result as fallback
        return games[0] if games else None

    except Exception as e:
        logger.log_warning(f"Error finding best search match: {e}")
        # Return first result as fallback
        try:
            if isinstance(search_results, dict) and "response" in search_results:
                games = search_results["response"].get("jeux", [])
                return games[0] if games else None
        except Exception:
            pass
        return None


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two game names.

    Args:
        name1: First name
        name2: Second name

    Returns:
        Similarity score between 0 and 1
    """
    if not name1 or not name2:
        return 0.0

    # Simple word-based similarity
    words1 = set(name1.split())
    words2 = set(name2.split())

    if not words1 or not words2:
        return 0.0

    # Calculate Jaccard similarity
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))

    return intersection / union if union > 0 else 0.0
