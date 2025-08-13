from logger import LoggerSingleton as logger


class ScraperError(Exception):
    """Base exception for scraper-related errors."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        logger.log_error(message)

    def get_message(self) -> str:
        """Get the error message safely."""
        # Use args[0] which is the standard way to access exception message
        # or fall back to the stored message or string representation
        if self.args:
            return str(self.args[0])
        elif hasattr(self, "message") and self.message:
            return str(self.message)
        else:
            return str(self)

    def __str__(self) -> str:
        """String representation of the exception."""
        return self.get_message()


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
