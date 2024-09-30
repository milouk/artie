import struct
import logging

# Set up logging
logging.basicConfig(level=logging.ERROR)

KEY_MAPPING = {
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

current_code = 0
current_code_name = ""
current_value = 0


def check_input(device_path="/dev/input/event1"):
    global current_code, current_code_name, current_value
    with open(device_path, "rb") as f:
        while True:
            event = f.read(24)
            if event:
                _, _, _, key_code, key_value = struct.unpack("llHHI", event)
                if key_value != 0:
                    if key_value != 1:
                        key_value = -1
                    current_code = key_code
                    current_code_name = KEY_MAPPING.get(current_code, str(current_code))
                    current_value = key_value
                    logging.debug(f"Key pressed: {current_code_name}, value: {current_value}")
                    return


def key_pressed(key_code_name, key_value=99):
    if current_code_name == key_code_name:
        if key_value != 99:
            return current_value == key_value
        return True


def reset_input():
    global current_code_name, current_value
    current_code_name = ""
    current_value = 0
    logging.debug("Input reset")
