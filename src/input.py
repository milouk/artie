"""Input handling module with proper resource management and state encapsulation."""

import errno
import os
import struct
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union

import exceptions
from logger import LoggerSingleton as logger


@dataclass
class InputState:
    """Encapsulates input state to avoid global variables."""

    current_code: int = 0
    current_code_name: str = ""
    current_value: int = 0


class InputManager:
    """Manages input handling with proper resource management."""

    # Key mapping for input events
    KEY_MAPPING: Dict[int, str] = {
        304: "A",
        305: "B",
        306: "Y",
        307: "X",
        308: "L1",
        309: "R1",
        314: "L2",
        315: "R2",
        17: "DY",
        16: "DX",
        310: "SELECT",
        311: "START",
        312: "MENUF",
        114: "V+",
        115: "V-",
    }

    def __init__(self, device_path: Union[str, Path] = "/dev/input/event1"):
        """
        Initialize input manager.

        Args:
            device_path: Path to input device
        """
        self.device_path = Path(device_path)
        self.state = InputState()
        self._nb_fd: int = -1  # Persistent fd for non-blocking reads
        self._validate_device()

    def _validate_device(self) -> None:
        """Validate that input device exists and is accessible."""
        if not self.device_path.exists():
            logger.log_warning(f"Input device not found: {self.device_path}")
            # Don't raise exception as this might be running in a test environment

    @contextmanager
    def _open_device(self):
        """Context manager for opening input device with proper error handling.

        Uses unbuffered IO (buffering=0) so that select() accurately reflects
        the kernel buffer state. With default buffering, Python reads ahead
        into an internal buffer, causing select() to report 'not ready' even
        when events remain unprocessed in the Python buffer.
        """
        try:
            with open(self.device_path, "rb", buffering=0) as device:
                yield device
        except (IOError, OSError) as e:
            raise exceptions.ScraperError(
                f"Error opening input device {self.device_path}: {e}"
            )

    def check_input(self) -> None:
        """
        Check for input events and update state.

        Raises:
            ScraperError: If device cannot be accessed
        """
        try:
            with self._open_device() as device:
                while True:
                    event_data = device.read(24)
                    if event_data:
                        if self._process_event(event_data):
                            return
        except exceptions.ScraperError:
            # Re-raise scraper errors
            raise
        except Exception as e:
            # Log other errors but don't crash the application
            logger.log_error(f"Unexpected error reading input: {e}")

    def _process_event(self, event_data: bytes) -> bool:
        """
        Process a single input event.

        Args:
            event_data: Raw event data from device

        Returns:
            True if event was processed and should return, False to continue reading
        """
        try:
            _, _, _, key_code, key_value = struct.unpack("llHHI", event_data)

            if key_value != 0:
                # Normalize key value
                normalized_value = -1 if key_value != 1 else 1

                # Update state
                self.state.current_code = key_code
                self.state.current_code_name = self.KEY_MAPPING.get(
                    key_code, f"UNKNOWN_{key_code}"
                )
                self.state.current_value = normalized_value

                logger.log_debug(
                    f"Key pressed: {self.state.current_code_name}, value: {self.state.current_value}",
                    extra_data={
                        "key_code": key_code,
                        "key_name": self.state.current_code_name,
                        "key_value": self.state.current_value,
                    },
                )

                return True

        except struct.error as e:
            logger.log_error(f"Error unpacking input event: {e}")
        except Exception as e:
            logger.log_error(f"Unexpected error processing input event: {e}")

        return False

    def start_nonblocking(self) -> None:
        """Open a persistent fd for non-blocking reads.

        Must be called before a polling loop (e.g. batch scraping) so that
        events are queued by the kernel between polls. Without a persistent
        fd, events that arrive between open/close cycles are lost because
        Linux evdev queues events per open file descriptor.
        """
        self.stop_nonblocking()  # Close any previous fd
        try:
            self._nb_fd = os.open(str(self.device_path), os.O_RDONLY | os.O_NONBLOCK)
        except OSError as e:
            logger.log_warning(f"Failed to open non-blocking input fd: {e}")
            self._nb_fd = -1

    def stop_nonblocking(self) -> None:
        """Close the persistent non-blocking fd."""
        if self._nb_fd >= 0:
            try:
                os.close(self._nb_fd)
            except OSError:
                pass
            self._nb_fd = -1

    def check_input_nonblocking(self) -> bool:
        """
        Non-blocking input check. Returns True if a key event was read.

        If a persistent fd was opened via start_nonblocking(), uses that fd
        so events are never lost between polls. Otherwise falls back to
        opening a temporary fd (original behavior).
        """
        if self._nb_fd >= 0:
            return self._drain_nonblocking(self._nb_fd)

        # Fallback: open a temporary fd (events between calls may be lost)
        if not self.device_path.exists():
            return False

        found_key = False
        fd = -1
        try:
            fd = os.open(str(self.device_path), os.O_RDONLY | os.O_NONBLOCK)
            found_key = self._drain_nonblocking(fd)
        except Exception:
            pass
        finally:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
        return found_key

    def _drain_nonblocking(self, fd: int) -> bool:
        """Drain all pending events from a non-blocking fd."""
        found_key = False
        try:
            while True:
                try:
                    event_data = os.read(fd, 24)
                except OSError as e:
                    if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        break
                    raise
                if len(event_data) < 24:
                    break
                if self._process_event(event_data):
                    found_key = True
        except Exception:
            pass
        return found_key

    def key_pressed(self, key_code_name: str, key_value: Optional[int] = None) -> bool:
        """
        Check if a specific key was pressed.

        Args:
            key_code_name: Name of the key to check
            key_value: Optional specific value to match (1 or -1)

        Returns:
            True if key was pressed with matching value, False otherwise
        """
        if self.state.current_code_name != key_code_name:
            return False

        if key_value is not None:
            return self.state.current_value == key_value

        return True

    def reset_input(self) -> None:
        """Reset input state."""
        self.state.current_code = 0
        self.state.current_code_name = ""
        self.state.current_value = 0
        logger.log_debug("Input state reset")

    def get_current_state(self) -> InputState:
        """Get current input state (read-only copy)."""
        return InputState(
            current_code=self.state.current_code,
            current_code_name=self.state.current_code_name,
            current_value=self.state.current_value,
        )


# Global input manager instance for backward compatibility
_global_input_manager: Optional[InputManager] = None


def _get_input_manager() -> InputManager:
    """Get global input manager instance."""
    global _global_input_manager
    if _global_input_manager is None:
        _global_input_manager = InputManager()
    return _global_input_manager


# Backward compatibility functions
def check_input(device_path: str = "/dev/input/event1") -> None:
    """Check for input events (backward compatibility function)."""
    manager = _get_input_manager()
    if str(manager.device_path) != device_path:
        # Create new manager if device path changed
        global _global_input_manager
        _global_input_manager = InputManager(device_path)
        manager = _global_input_manager

    manager.check_input()
    # Update legacy variables after checking input
    _update_legacy_variables()


def key_pressed(key_code_name: str, key_value: Optional[int] = None) -> bool:
    """Check if key was pressed (backward compatibility function)."""
    manager = _get_input_manager()
    # Convert legacy key_value=99 to None for backward compatibility
    if key_value == 99:
        key_value = None
    return manager.key_pressed(key_code_name, key_value)


def start_nonblocking() -> None:
    """Open persistent non-blocking fd (backward compatibility function)."""
    _get_input_manager().start_nonblocking()


def stop_nonblocking() -> None:
    """Close persistent non-blocking fd (backward compatibility function)."""
    _get_input_manager().stop_nonblocking()


def check_input_nonblocking() -> bool:
    """Non-blocking input check (backward compatibility function)."""
    manager = _get_input_manager()
    result = manager.check_input_nonblocking()
    if result:
        _update_legacy_variables()
    return result


def reset_input() -> None:
    """Reset input state (backward compatibility function)."""
    manager = _get_input_manager()
    manager.reset_input()
    # Update legacy variables after reset
    _update_legacy_variables()


# Legacy global variable access for backward compatibility
# These are accessed as module-level variables in app.py
current_code = 0
current_code_name = ""
current_value = 0


def _update_legacy_variables():
    """Update legacy module-level variables from input manager state."""
    global current_code, current_code_name, current_value
    manager = _get_input_manager()
    current_code = manager.state.current_code
    current_code_name = manager.state.current_code_name
    current_value = manager.state.current_value
