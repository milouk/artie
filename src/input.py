"""Input handling module using pygame events (keyboard + joystick)."""

import threading
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pygame

from logger import LoggerSingleton as logger


@dataclass
class InputState:
    """Encapsulates input state to avoid global variables."""

    current_code: int = 0
    current_code_name: str = ""
    current_value: int = 0


class InputManager:
    """Manages input via pygame events (keyboard + joystick)."""

    # Keyboard mapping — used for desktop testing and gptokeyb-mapped keys
    KEYBOARD_MAP: Dict[int, Tuple[str, int]] = {
        pygame.K_UP: ("DY", -1),
        pygame.K_DOWN: ("DY", 1),
        pygame.K_LEFT: ("DX", -1),
        pygame.K_RIGHT: ("DX", 1),
        pygame.K_RETURN: ("A", 1),
        pygame.K_SPACE: ("A", 1),
        pygame.K_ESCAPE: ("B", 1),
        pygame.K_BACKSPACE: ("B", 1),
        pygame.K_y: ("Y", 1),
        pygame.K_x: ("X", 1),
        pygame.K_q: ("L1", 1),
        pygame.K_e: ("R1", 1),
        pygame.K_1: ("L2", 1),
        pygame.K_2: ("R2", 1),
        pygame.K_TAB: ("SELECT", 1),
        pygame.K_s: ("START", 1),
        pygame.K_m: ("MENUF", 1),
    }

    # Joystick button mapping — muOS-Keys virtual joystick
    # From gamecontrollerdb.txt: a:b3,b:b4,x:b6,y:b5,leftshoulder:b7,
    # rightshoulder:b8,lefttrigger:b13,righttrigger:b14,guide:b11,
    # start:b10,back:b9
    JOYSTICK_BUTTON_MAP: Dict[int, str] = {
        3: "A",
        4: "B",
        5: "Y",
        6: "X",
        7: "L1",
        8: "R1",
        9: "SELECT",
        10: "START",
        11: "MENUF",
        13: "L2",
        14: "R2",
    }

    AXIS_DEADZONE = 0.5

    def __init__(self):
        self.state = InputState()
        self._joystick: Optional[pygame.joystick.Joystick] = None
        self._init_joystick()

    def _init_joystick(self):
        """Detect and initialize the first joystick/gamepad."""
        try:
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self._joystick = pygame.joystick.Joystick(0)
                self._joystick.init()
                logger.log_info(
                    f"Joystick detected: {self._joystick.get_name()}"
                )
            else:
                logger.log_info("No joystick detected — using keyboard input")
        except pygame.error as e:
            logger.log_warning(f"Joystick init failed: {e}")

    def check_input(self) -> None:
        """Block until a meaningful input event occurs."""
        while True:
            event = pygame.event.wait()
            if self._process_event(event):
                return

    def check_input_nonblocking(self) -> bool:
        """Drain pending events. Returns True if a key event was found."""
        found = False
        for event in pygame.event.get():
            if self._process_event(event):
                found = True
        return found

    def _process_event(self, event) -> bool:
        """Process a single pygame event. Returns True for meaningful input."""
        if event.type == pygame.KEYDOWN:
            mapping = self.KEYBOARD_MAP.get(event.key)
            if mapping:
                self.state.current_code_name = mapping[0]
                self.state.current_value = mapping[1]
                self.state.current_code = event.key
                logger.log_debug(
                    f"Key pressed: {mapping[0]}, value: {mapping[1]}"
                )
                return True

        elif event.type == pygame.JOYBUTTONDOWN:
            btn_name = self.JOYSTICK_BUTTON_MAP.get(event.button)
            if btn_name:
                self.state.current_code_name = btn_name
                self.state.current_value = 1
                self.state.current_code = event.button
                logger.log_debug(f"Button pressed: {btn_name}")
                return True

        elif event.type == pygame.JOYHATMOTION:
            hat_x, hat_y = event.value
            if hat_y != 0:
                self.state.current_code_name = "DY"
                # pygame hat: up=1, down=-1; app expects: up=-1, down=1
                self.state.current_value = -hat_y
                self.state.current_code = 17
                return True
            if hat_x != 0:
                self.state.current_code_name = "DX"
                self.state.current_value = hat_x
                self.state.current_code = 16
                return True

        elif event.type == pygame.JOYAXISMOTION:
            if event.axis in (0, 1) and abs(event.value) > self.AXIS_DEADZONE:
                if event.axis == 1:  # Y axis (up/down)
                    self.state.current_code_name = "DY"
                    self.state.current_value = 1 if event.value > 0 else -1
                    self.state.current_code = 17
                    return True
                else:  # X axis (left/right)
                    self.state.current_code_name = "DX"
                    self.state.current_value = 1 if event.value > 0 else -1
                    self.state.current_code = 16
                    return True

        elif event.type == pygame.QUIT:
            self.state.current_code_name = "MENUF"
            self.state.current_value = 1
            self.state.current_code = 0
            return True

        return False

    def key_pressed(self, key_code_name: str, key_value: Optional[int] = None) -> bool:
        if self.state.current_code_name != key_code_name:
            return False
        if key_value is not None:
            return self.state.current_value == key_value
        return True

    def reset_input(self) -> None:
        self.state = InputState()
        logger.log_debug("Input state reset")

    def get_current_state(self) -> InputState:
        return InputState(
            current_code=self.state.current_code,
            current_code_name=self.state.current_code_name,
            current_value=self.state.current_value,
        )

    # No-ops — pygame manages its own event queue and resources
    def open_persistent(self) -> None:
        pass

    def close_persistent(self) -> None:
        pass

    def start_nonblocking(self) -> None:
        pass

    def stop_nonblocking(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Singleton + backward-compatible module-level API
# ---------------------------------------------------------------------------

_global_input_manager: Optional[InputManager] = None
_input_manager_lock = threading.Lock()


def _get_input_manager() -> InputManager:
    """Get global input manager instance (thread-safe)."""
    global _global_input_manager
    if _global_input_manager is None:
        with _input_manager_lock:
            if _global_input_manager is None:
                _global_input_manager = InputManager()
    return _global_input_manager


def check_input(device_path: str = "/dev/input/event1") -> None:
    """Check for input events (backward compatibility function)."""
    _get_input_manager().check_input()
    _update_legacy_variables()


def key_pressed(key_code_name: str, key_value: Optional[int] = None) -> bool:
    """Check if key was pressed (backward compatibility function)."""
    if key_value == 99:
        key_value = None
    return _get_input_manager().key_pressed(key_code_name, key_value)


def open_persistent() -> None:
    _get_input_manager().open_persistent()


def close_persistent() -> None:
    _get_input_manager().close_persistent()


def start_nonblocking() -> None:
    _get_input_manager().start_nonblocking()


def stop_nonblocking() -> None:
    _get_input_manager().stop_nonblocking()


def check_input_nonblocking() -> bool:
    manager = _get_input_manager()
    result = manager.check_input_nonblocking()
    if result:
        _update_legacy_variables()
    return result


def reset_input() -> None:
    manager = _get_input_manager()
    manager.reset_input()
    _update_legacy_variables()


# Legacy global variable access — read by app.py as module-level attributes
current_code = 0
current_code_name = ""
current_value = 0


def _update_legacy_variables():
    """Sync module-level variables from input manager state."""
    global current_code, current_code_name, current_value
    manager = _get_input_manager()
    current_code = manager.state.current_code
    current_code_name = manager.state.current_code_name
    current_value = manager.state.current_value
