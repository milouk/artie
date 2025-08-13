"""Infrastructure API module for ScreenScraper server monitoring."""

import base64
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode, urlparse, urlunparse

import exceptions
from cache_manager import api_cached
from logger import LoggerSingleton as logger
from scraper import fetch_data

INFRA_URL = "https://api.screenscraper.fr/api2/ssinfraInfos.php"


def parse_infrastructure_url(
    dev_id: str, dev_password: str, username: str, password: str
) -> str:
    """
    Build infrastructure info API URL.

    Args:
        dev_id: Developer ID (base64 encoded)
        dev_password: Developer password (base64 encoded)
        username: Username
        password: Password

    Returns:
        Complete infrastructure info URL

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

        return urlunparse(urlparse(INFRA_URL)._replace(query=urlencode(params)))

    except (UnicodeDecodeError, Exception) as e:
        raise exceptions.ScraperError(f"Error encoding infrastructure URL: {e}")


@api_cached(ttl=300)  # Cache infrastructure info for 5 minutes
def get_infrastructure_info(
    dev_id: str, dev_password: str, username: str, password: str
) -> Optional[Dict[str, Any]]:
    """
    Get server infrastructure information from ScreenScraper API.

    Args:
        dev_id: Developer ID (base64 encoded)
        dev_password: Developer password (base64 encoded)
        username: Username
        password: Password

    Returns:
        Infrastructure data from API or None if failed

    Raises:
        RateLimitError: When API quota is exceeded
        ForbiddenError: When API access is forbidden
        ScraperError: For other API errors
    """
    try:
        logger.log_info("Fetching infrastructure info from ScreenScraper API")

        infra_url = parse_infrastructure_url(dev_id, dev_password, username, password)
        infra_data = fetch_data(infra_url)

        if not infra_data:
            logger.log_warning("No infrastructure data received from API")
            return None

        # Validate response structure
        if isinstance(infra_data, dict) and "response" in infra_data:
            response = infra_data["response"]
            if "ssinfra" in response:
                logger.log_info("Successfully retrieved infrastructure information")
                return infra_data
            else:
                logger.log_warning("Infrastructure data missing from API response")
                return None
        else:
            logger.log_warning("Unexpected infrastructure API response structure")
            return None

    except (
        exceptions.RateLimitError,
        exceptions.ForbiddenError,
        exceptions.ScraperError,
    ):
        # Re-raise API errors
        raise
    except Exception as e:
        logger.log_error(f"Unexpected error fetching infrastructure info: {e}")
        raise exceptions.ScraperError(f"Infrastructure info fetch failed: {e}")


def calculate_optimal_threads(
    infra_info: Optional[Dict[str, Any]],
    user_max_threads: int,
    current_threads: int = 10,
) -> Tuple[int, str]:
    """
    Calculate optimal thread count based on server capacity and user limits.

    Args:
        infra_info: Infrastructure information from API
        user_max_threads: Maximum threads allowed for user
        current_threads: Current configured thread count

    Returns:
        Tuple of (optimal_threads, reason)
    """
    try:
        if not infra_info or "response" not in infra_info:
            logger.log_info("No infrastructure data available, using user maximum")
            return user_max_threads, "No server data available"

        response = infra_info["response"]
        ssinfra = response.get("ssinfra", {})

        if not ssinfra:
            logger.log_info("No infrastructure details available, using user maximum")
            return user_max_threads, "No server details available"

        # Extract server metrics
        server_load = ssinfra.get("charge", 0)  # Server load percentage
        max_threads = ssinfra.get("maxthreads", 10)  # Server max threads
        current_threads_server = ssinfra.get(
            "threadsactifs", 0
        )  # Currently active threads

        logger.log_info(
            f"Server metrics - Load: {server_load}%, Max threads: {max_threads}, Active: {current_threads_server}"
        )

        # Calculate optimal threads based on server load
        optimal_threads = user_max_threads
        reason = "Using user maximum"

        # Reduce threads if server is heavily loaded
        if isinstance(server_load, (int, float)):
            if server_load > 90:
                optimal_threads = max(1, user_max_threads // 4)
                reason = f"Server heavily loaded ({server_load}%)"
            elif server_load > 75:
                optimal_threads = max(1, user_max_threads // 2)
                reason = f"Server moderately loaded ({server_load}%)"
            elif server_load > 50:
                optimal_threads = max(1, int(user_max_threads * 0.75))
                reason = f"Server somewhat loaded ({server_load}%)"

        # Consider server thread capacity
        if isinstance(max_threads, (int, float)) and max_threads > 0:
            if isinstance(current_threads_server, (int, float)):
                available_threads = max_threads - current_threads_server
                if available_threads < optimal_threads:
                    optimal_threads = max(
                        1, int(available_threads * 0.8)
                    )  # Use 80% of available
                    reason = f"Limited server capacity ({available_threads} threads available)"

        # Ensure we don't exceed user limits
        optimal_threads = min(optimal_threads, user_max_threads)

        # Ensure minimum of 1 thread
        optimal_threads = max(1, optimal_threads)

        logger.log_info(f"Calculated optimal threads: {optimal_threads} ({reason})")
        return optimal_threads, reason

    except Exception as e:
        logger.log_warning(f"Error calculating optimal threads: {e}")
        return user_max_threads, "Calculation error, using user maximum"


def get_server_status(infra_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract server status information from infrastructure data.

    Args:
        infra_info: Infrastructure information from API

    Returns:
        Dictionary with server status details
    """
    status = {
        "available": False,
        "load_percentage": None,
        "max_threads": None,
        "active_threads": None,
        "api_version": None,
        "server_time": None,
        "status_message": "No data available",
    }

    try:
        if not infra_info or "response" not in infra_info:
            return status

        response = infra_info["response"]
        ssinfra = response.get("ssinfra", {})

        if not ssinfra:
            return status

        # Extract available information
        status["available"] = True
        status["load_percentage"] = ssinfra.get("charge")
        status["max_threads"] = ssinfra.get("maxthreads")
        status["active_threads"] = ssinfra.get("threadsactifs")

        # Get API version from header if available
        header = infra_info.get("header", {})
        status["api_version"] = header.get("APIversion")
        status["server_time"] = header.get("commandedate")

        # Generate status message
        load = status["load_percentage"]
        if isinstance(load, (int, float)):
            if load > 90:
                status["status_message"] = f"Server heavily loaded ({load}%)"
            elif load > 75:
                status["status_message"] = f"Server moderately loaded ({load}%)"
            elif load > 50:
                status["status_message"] = f"Server somewhat loaded ({load}%)"
            else:
                status["status_message"] = f"Server running normally ({load}%)"
        else:
            status["status_message"] = "Server status available"

        return status

    except Exception as e:
        logger.log_warning(f"Error extracting server status: {e}")
        status["status_message"] = f"Error reading status: {e}"
        return status


def should_reduce_load(
    infra_info: Optional[Dict[str, Any]], threshold: float = 80.0
) -> bool:
    """
    Determine if load should be reduced based on server status.

    Args:
        infra_info: Infrastructure information from API
        threshold: Load percentage threshold for reduction

    Returns:
        True if load should be reduced, False otherwise
    """
    try:
        if not infra_info or "response" not in infra_info:
            return False

        response = infra_info["response"]
        ssinfra = response.get("ssinfra", {})

        if not ssinfra:
            return False

        server_load = ssinfra.get("charge")

        if isinstance(server_load, (int, float)):
            return server_load > threshold

        return False

    except Exception as e:
        logger.log_warning(f"Error checking load reduction need: {e}")
        return False


def get_recommended_delay(infra_info: Optional[Dict[str, Any]]) -> float:
    """
    Get recommended delay between requests based on server load.

    Args:
        infra_info: Infrastructure information from API

    Returns:
        Recommended delay in seconds
    """
    try:
        if not infra_info or "response" not in infra_info:
            return 1.0  # Default delay

        response = infra_info["response"]
        ssinfra = response.get("ssinfra", {})

        if not ssinfra:
            return 1.0

        server_load = ssinfra.get("charge", 0)

        if isinstance(server_load, (int, float)):
            if server_load > 90:
                return 5.0  # 5 second delay for heavy load
            elif server_load > 75:
                return 3.0  # 3 second delay for moderate load
            elif server_load > 50:
                return 2.0  # 2 second delay for some load
            else:
                return 1.0  # 1 second delay for normal load

        return 1.0  # Default delay

    except Exception as e:
        logger.log_warning(f"Error calculating recommended delay: {e}")
        return 1.0
