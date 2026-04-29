class ScraperError(Exception):
    """Base exception for scraper-related errors."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ForbiddenError(ScraperError):
    """Exception raised when API returns 403 Forbidden."""

    pass


class RateLimitError(ScraperError):
    """Exception raised when API rate limit is exceeded."""

    pass


class APIClosedError(ScraperError):
    """Exception for 401 - API closed for non-members."""

    pass


class APIFullyClosedError(ScraperError):
    """Exception for 423 - API fully closed (server problems)."""

    pass


class SoftwareBlacklistedError(ScraperError):
    """Exception for 426 - Software blacklisted/obsolete."""

    pass


class ThreadLimitError(RateLimitError):
    """Exception for 429 - Thread limit variations."""

    pass


class TooManyUnrecognizedError(ScraperError):
    """Exception for 431 - Too many unrecognized ROMs."""

    pass


class BadRequestError(ScraperError):
    """Exception for 400 - Bad request/malformed URL."""

    pass


class ConfigurationError(ScraperError):
    """Exception raised for configuration-related errors."""

    pass


class MediaProcessingError(ScraperError):
    """Exception raised for media processing errors."""

    pass


class NetworkError(ScraperError):
    """Exception raised for network-related errors."""

    pass


class ResourceNotFoundError(ScraperError):
    """Exception raised when the API returns 404 for a ROM lookup.

    Distinct from generic ScraperError so callers like get_game_data can
    react specifically (e.g. fall back to a search-by-name lookup) without
    swallowing real failures.
    """

    pass
