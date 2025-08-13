"""Enhanced logging module with structured logging and performance monitoring."""

import json
import logging
import logging.handlers
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structured data."""
        # Base log data
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class PerformanceLogger:
    """Logger for performance monitoring."""

    def __init__(self, logger_instance: logging.Logger):
        self.logger = logger_instance
        self._timers: Dict[str, float] = {}

    def start_timer(self, name: str) -> None:
        """Start a performance timer."""
        self._timers[name] = time.time()

    def end_timer(
        self, name: str, extra_data: Optional[Dict[str, Any]] = None
    ) -> float:
        """End a performance timer and log the duration."""
        if name not in self._timers:
            self.logger.warning(f"Timer '{name}' was not started")
            return 0.0

        duration = time.time() - self._timers[name]
        del self._timers[name]

        log_data = {
            "timer_name": name,
            "duration_seconds": round(duration, 4),
            "duration_ms": round(duration * 1000, 2),
        }

        if extra_data:
            log_data.update(extra_data)

        self.logger.info(
            f"Performance: {name} completed", extra={"extra_data": log_data}
        )
        return duration

    @contextmanager
    def timer(self, name: str, extra_data: Optional[Dict[str, Any]] = None):
        """Context manager for timing operations."""
        self.start_timer(name)
        try:
            yield
        finally:
            self.end_timer(name, extra_data)


class LoggerSingleton:
    """Enhanced singleton logger with structured logging and performance monitoring."""

    _logger_instance: Optional[logging.Logger] = None
    _performance_logger: Optional[PerformanceLogger] = None
    _log_level = logging.INFO
    _structured_logging = False

    @classmethod
    def setup_logger(
        cls,
        log_level: int = logging.INFO,
        log_file: Optional[str] = None,
        structured: bool = False,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ) -> None:
        """
        Setup logger with enhanced configuration options.

        Args:
            log_level: Logging level
            log_file: Optional log file path
            structured: Whether to use structured JSON logging
            max_file_size: Maximum log file size before rotation
            backup_count: Number of backup files to keep
        """
        cls._log_level = log_level
        cls._structured_logging = structured

        if cls._logger_instance is None:
            cls._initialize_logger(log_file, structured, max_file_size, backup_count)
        else:
            cls._logger_instance.setLevel(cls._log_level)

    @classmethod
    def _initialize_logger(
        cls,
        log_file: Optional[str] = None,
        structured: bool = False,
        max_file_size: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ) -> None:
        """Initialize logger with handlers and formatters."""
        cls._logger_instance = logging.getLogger("ArtieScraperLogger")
        cls._logger_instance.setLevel(cls._log_level)

        # Clear existing handlers
        cls._logger_instance.handlers.clear()

        # Choose formatter
        if structured:
            formatter = StructuredFormatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s"
            )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(cls._log_level)
        console_handler.setFormatter(formatter)
        cls._logger_instance.addHandler(console_handler)

        # File handler with rotation if specified
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=max_file_size, backupCount=backup_count
            )
            file_handler.setLevel(cls._log_level)
            file_handler.setFormatter(formatter)
            cls._logger_instance.addHandler(file_handler)

        # Initialize performance logger
        cls._performance_logger = PerformanceLogger(cls._logger_instance)

    @classmethod
    def get_logger(cls) -> logging.Logger:
        """Get logger instance."""
        if cls._logger_instance is None:
            cls._initialize_logger()

        assert cls._logger_instance is not None, "Logger instance is not initialized"
        return cls._logger_instance

    @classmethod
    def get_performance_logger(cls) -> PerformanceLogger:
        """Get performance logger instance."""
        if cls._performance_logger is None:
            cls.get_logger()  # This will initialize both loggers

        assert (
            cls._performance_logger is not None
        ), "Performance logger is not initialized"
        return cls._performance_logger

    @classmethod
    def log_info(
        cls, message: str, extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log info message with optional structured data."""
        logger = cls.get_logger()
        extra = {"extra_data": extra_data} if extra_data else {}
        logger.info(message, extra=extra)

    @classmethod
    def log_debug(
        cls, message: str, extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log debug message with optional structured data."""
        logger = cls.get_logger()
        extra = {"extra_data": extra_data} if extra_data else {}
        logger.debug(message, extra=extra)

    @classmethod
    def log_warning(
        cls, message: str, extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log warning message with optional structured data."""
        logger = cls.get_logger()
        extra = {"extra_data": extra_data} if extra_data else {}
        logger.warning(message, extra=extra)

    @classmethod
    def log_error(
        cls, message: str, extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log error message with optional structured data."""
        logger = cls.get_logger()
        extra = {"extra_data": extra_data} if extra_data else {}
        logger.error(message, extra=extra)

    @classmethod
    def log_exception(
        cls, message: str, extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log exception with traceback and optional structured data."""
        logger = cls.get_logger()
        extra = {"extra_data": extra_data} if extra_data else {}
        logger.exception(message, extra=extra)

    @classmethod
    def log_performance(
        cls,
        operation: str,
        duration: float,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log performance metrics."""
        perf_data = {
            "operation": operation,
            "duration_seconds": round(duration, 4),
            "duration_ms": round(duration * 1000, 2),
        }

        if extra_data:
            perf_data.update(extra_data)

        cls.log_info(f"Performance: {operation}", perf_data)

    @classmethod
    def timer(cls, name: str, extra_data: Optional[Dict[str, Any]] = None):
        """Get timer context manager for performance logging."""
        perf_logger = cls.get_performance_logger()
        return perf_logger.timer(name, extra_data)
