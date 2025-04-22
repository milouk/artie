import threading
import struct
import select
import os
import signal
import time
from fcntl import fcntl, F_SETFL
from collections import defaultdict

# button codes
A = 304
B = 305
Y = 306
X = 307
L1 = 308
R1 = 309
L2 = 314
R2 = 315
DY = 17
DX = 16
SELECT = 310
START = 311
MENU = 312
VUP = 114
VDOWN = 115

# Input device configuration
INPUT_DEVICE = "/dev/input/event1"
EVENT_SIZE = 24

# Global state with thread-safe access
input_lock = threading.Lock()
active_buttons = defaultdict(bool)
should_exit = False
last_button = 0
button_time = 0.0
hold_time = 0.0


def input_worker():
    global active_buttons, should_exit, last_button

    fd = os.open(INPUT_DEVICE, os.O_RDWR)
    fcntl(fd, F_SETFL, os.O_NONBLOCK)

    try:
        while not should_exit:
            r, _, _ = select.select([fd], [], [], None)
            if not r:
                continue

            # Read all available events
            data = os.read(fd, EVENT_SIZE * 10)
            for i in range(0, len(data), EVENT_SIZE):
                event = data[i:i + EVENT_SIZE]
                if len(event) < EVENT_SIZE:
                    break

                _, _, ev_type, code, value = struct.unpack("llHHi", event)

                if ev_type != 1 and ev_type != 3:
                    continue

                with input_lock:
                    key = (code, value)
                    if value == 0:  # Toggle off the button
                        for k in list(active_buttons.keys()):
                            if k[0] == code:
                                active_buttons[k] = True
                    else:
                        active_buttons[key] = False

    finally:
        os.close(fd)


def start_input_thread():
    thread = threading.Thread(target=input_worker, daemon=True)
    thread.start()
    return thread


def key_pressed(code, key_value=1):
    global last_button, button_time, hold_time
    with input_lock:
        if (code, key_value) in active_buttons:  # our button has an event
            if active_buttons[(code, key_value)]:  # a button that has just toggled of!
                del active_buttons[(code, key_value)]  # remove that button
                if last_button == code and time.time() - button_time < 0.3:  # return False if already triggered recent
                    last_button = 0
                    return False
                else:  # Return True if it wasn't recently triggered (quick button tap)
                    last_button = 0
                    return True
            button_time = time.time()
            if last_button != code:  # This button was freshly activated
                hold_time = time.time()
                last_button = code
                return True
            if time.time() - hold_time < 0.3:  # wait a brief moment before scrolling
                return False
            return True
        return False


def reset_input():
    global active_buttons
    with input_lock:
        active_buttons.clear()


def cleanup(signum, frame):
    global should_exit
    should_exit = True


# Set up signal handling for clean exit
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)
