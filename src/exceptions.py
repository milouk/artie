from logger import LoggerSingleton as logger


class ScraperError(Exception):
    def __init__(self, message):
        super().__init__(message)
        logger.log_error(message)

    def get_message(self):
        s, _ = getattr(self, "message", str(self)), getattr(self, "message", repr(self))
        return s


class ForbiddenError(ScraperError):
    pass


class RateLimitError(ScraperError):
    pass
