import logging
from typing import Optional


class LoggerSingleton:
    _logger_instance: Optional[logging.Logger] = None
    _log_level = logging.INFO

    @classmethod
    def setup_logger(cls, log_level=logging.INFO):
        cls._log_level = log_level
        if cls._logger_instance is None:
            cls._initialize_logger()
        else:
            cls._logger_instance.setLevel(cls._log_level)

    @classmethod
    def _initialize_logger(cls):
        logging.basicConfig(
            level=cls._log_level, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        cls._logger_instance = logging.getLogger("AppLogger")
        cls._logger_instance.setLevel(cls._log_level)

    @classmethod
    def get_logger(cls) -> logging.Logger:
        if cls._logger_instance is None:
            cls._initialize_logger()

        assert cls._logger_instance is not None, "Logger instance is not initialized"
        return cls._logger_instance

    @classmethod
    def log_info(cls, message: str):
        logger = cls.get_logger()
        logger.info(message)

    @classmethod
    def log_debug(cls, message: str):
        logger = cls.get_logger()
        logger.debug(message)

    @classmethod
    def log_warning(cls, message: str):
        logger = cls.get_logger()
        logger.warning(message)

    @classmethod
    def log_error(cls, message: str):
        logger = cls.get_logger()
        logger.error(message)
