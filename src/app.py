import concurrent.futures
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import List

import input
from graphic import GUI
from logger import LoggerSingleton as logger
from PIL import Image
from scraper import (
    check_destination,
    fetch_box,
    fetch_preview,
    fetch_synopsis,
    get_game_data,
    get_image_files_without_extension,
    get_txt_files_without_extension,
    get_user_data,
)

VERSION = "1.0.5"

selected_position = 0
roms_selected_position = 0
selected_system = ""
current_window = "emulators"
max_elem = 11
skip_input_check = False


class Rom:
    def __init__(self, name, filename, path):
        self.name = name
        self.filename = filename
        self.path = path


class App:
    LOG_WAIT = 2

    def __init__(self):
        self.config = {}
        self.systems_mapping = {}
        self.roms_path = ""
        self.systems_logo_path = ""
        self.content = {}
        self.box_enabled = True
        self.preview_enabled = True
        self.synopsis_enabled = True
        self.threads = 1
        self.username = ""
        self.password = ""
        self.gui = GUI()

    def load_config(self, config_file):
        with open(config_file, "r") as file:
            file_contents = file.read()

        try:
            self.config = json.loads(file_contents)
        except json.JSONDecodeError as e:
            logger.log_error(f"Error loading config file: {e}")
            self.gui.draw_log("Your config.json file is not a valid json file...")
            self.gui.draw_paint()
            time.sleep(self.LOG_WAIT)
            sys.exit()

        self.roms_path = self.config.get("roms")
        self.systems_logo_path = self.config.get("logos")
        self.colors = self.config.get("colors")
        self.dev_id = self.config.get("screenscraper").get("devid")
        self.dev_password = self.config.get("screenscraper").get("devpassword")
        self.username = self.config.get("screenscraper").get("username")
        self.password = self.config.get("screenscraper").get("password")
        self.threads = self.config.get("screenscraper").get("threads")
        self.content = self.config.get("screenscraper").get("content")
        self.box_enabled = self.content["box"]["enabled"]
        self.preview_enabled = self.content["preview"]["enabled"]
        self.synopsis_enabled = self.content["synopsis"]["enabled"]
        self.get_user_threads()
        for system in self.config["screenscraper"]["systems"]:
            self.systems_mapping[system["dir"].lower()] = system

        self.gui.COLOR_PRIMARY = self.colors.get("primary")
        self.gui.COLOR_PRIMARY_DARK = self.colors.get("primary_dark")
        self.gui.COLOR_SECONDARY = self.colors.get("secondary")
        self.gui.COLOR_SECONDARY_LIGHT = self.colors.get("secondary_light")
        self.gui.COLOR_SECONDARY_DARK = self.colors.get("secondary_dark")

    def setup_logging(self):
        log_level_str = self.config.get("log_level", "INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
        logger.setup_logger(log_level)

    def start(self, config_file: str) -> None:
        self.load_config(config_file)
        self.setup_logging()
        logger.log_debug(f"Artie Scraper v{VERSION}")
        self.gui.draw_start()
        self.gui.screen_reset()
        main_gui = self.gui.create_image()
        self.gui.draw_active(main_gui)
        self.load_emulators()

    def update(self) -> None:
        global skip_input_check, current_window
        if skip_input_check:
            input.reset_input()
            skip_input_check = False
        else:
            input.check_input()

        if input.key_pressed("MENUF"):
            self.gui.draw_end()
            sys.exit()

        if current_window == "emulators":
            self.load_emulators()
        elif current_window == "roms":
            self.load_roms()

    def get_available_systems(self) -> List[str]:
        available_systems = [
            d.lower()
            for d in os.listdir(self.roms_path)
            if Path(self.roms_path, d).is_dir()
        ]
        return sorted(
            [system for system in available_systems if system in self.systems_mapping]
        )

    def get_roms(self, system: str) -> list[Rom]:
        roms = []
        system_path = Path(self.roms_path) / system

        for root, dirs, files in os.walk(system_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for file in files:
                file_path = Path(root) / file
                if file.startswith("."):
                    continue
                if file_path.is_file() and self.is_valid_rom(file):
                    name = file_path.stem
                    rom = Rom(filename=file, name=name, path=file_path)
                    roms.append(rom)
        return roms

    def delete_files_in_directory(self, filenames, directory_path):
        directory = Path(directory_path)
        if directory.is_dir():
            for file in directory.iterdir():
                if file.is_file() and file.stem in filenames:
                    file.unlink()

    def delete_system_media(self) -> None:
        global selected_system
        system = self.systems_mapping.get(selected_system)
        if system:
            roms = [rom.name for rom in self.get_roms(selected_system)]
            media_types = []
            if self.box_enabled:
                media_types.append("box")
            if self.preview_enabled:
                media_types.append("preview")
            if self.synopsis_enabled:
                media_types.append("synopsis")
            for media_type in media_types:
                self.delete_files_in_directory(roms, system.get(media_type, ""))

    def draw_available_systems(self, available_systems: List[str]) -> None:
        max_elem = 11
        start_idx = (selected_position // max_elem) * max_elem
        end_idx = start_idx + max_elem
        for i, system in enumerate(available_systems[start_idx:end_idx]):
            logo = f"{self.systems_logo_path}/{system}.png"
            self.row_list(
                system, (20, 50 + (i * 35)), 600, i == (selected_position % max_elem)
            )

        self.button_circle((30, 450), "A", "Select")
        self.button_circle((170, 450), "X", "Delete")

    def load_emulators(self) -> None:
        global selected_position, selected_system, current_window, skip_input_check

        self.gui.draw_clear()
        self.gui.draw_rectangle_r([10, 40, 630, 440], 15)
        self.gui.draw_text((320, 20), f"Artie Scraper v{VERSION}", anchor="mm")

        if not Path(self.roms_path).exists() or not any(Path(self.roms_path).iterdir()):
            self.gui.draw_log("Wrong Roms path, check config.json")
            self.gui.draw_paint()
            time.sleep(self.LOG_WAIT)
            sys.exit()

        available_systems = self.get_available_systems()

        if available_systems:
            if input.key_pressed("DY"):
                if input.current_value == 1:
                    if selected_position < len(available_systems) - 1:
                        selected_position += 1
                elif input.current_value == -1:
                    if selected_position > 0:
                        selected_position -= 1
            elif input.key_pressed("A"):
                selected_system = available_systems[selected_position]
                current_window = "roms"
                self.gui.draw_log("Checking existing media...")
                self.gui.draw_paint()
                skip_input_check = True
                return
            elif input.key_pressed("X"):
                selected_system = available_systems[selected_position]
                self.delete_system_media()
                self.gui.draw_log(f"Deleting all existing {selected_system} media...")
                self.gui.draw_paint()
                skip_input_check = True
                time.sleep(self.LOG_WAIT)
                return
            elif input.key_pressed("L1"):
                if selected_position > 0:
                    selected_position = max(0, selected_position - max_elem)
            elif input.key_pressed("R1"):
                if selected_position < len(available_systems) - 1:
                    selected_position = min(
                        len(available_systems) - 1, selected_position + max_elem
                    )
            elif input.key_pressed("L2"):
                if selected_position > 0:
                    selected_position = max(0, selected_position - 100)
            elif input.key_pressed("R2"):
                if selected_position < len(available_systems) - 1:
                    selected_position = min(
                        len(available_systems) - 1, selected_position + 100
                    )

        if len(available_systems) >= 1:
            self.draw_available_systems(available_systems)
        else:
            self.gui.draw_text(
                (320, 240), f"No Emulators found in {self.roms_path}", anchor="mm"
            )

        self.button_circle((300, 450), "M", "Exit")

        self.gui.draw_paint()

    def is_valid_rom(self, rom):
        invalid_extensions = {
            ".cue",
            ".m3u",
            ".jpg",
            ".png",
            ".img",
            ".sub",
            ".db",
            ".xml",
            ".txt",
            ".dat",
            ".mp4",
            ".pdf",
            ".inf",
        }
        return os.path.splitext(rom)[1] not in invalid_extensions

    def save_file_to_disk(self, data, destination):
        check_destination(destination)
        destination.write_bytes(data)
        logger.log_debug(f"Saved file to {destination}")
        return True

    def get_user_threads(self):
        user_info = get_user_data(
            self.dev_id,
            self.dev_password,
            self.username,
            self.password,
        )
        if not user_info:
            self.threads = 1
        else:
            self.threads = min(self.threads, int(user_info["response"]["ssuser"]["maxthreads"]))
        logger.log_info(f"number of threads: {self.threads}")

    def scrape(self, rom, system_id):
        scraped_box = scraped_preview = scraped_synopsis = None
        try:
            game = get_game_data(
                system_id,
                rom.path,
                self.dev_id,
                self.dev_password,
                self.username,
                self.password,
            )

            if game:
                content = self.content
                if self.box_enabled:
                    scraped_box = fetch_box(game, content)
                if self.preview_enabled:
                    scraped_preview = fetch_preview(game, content)
                if self.synopsis_enabled:
                    scraped_synopsis = fetch_synopsis(game, content)
        except Exception as e:
            logger.log_error(f"Error scraping {rom.name}: {e}")

        return scraped_box, scraped_preview, scraped_synopsis

    def process_rom(self, rom, system_id, box_dir, preview_dir, synopsis_dir):
        scraped_box, scraped_preview, scraped_synopsis = self.scrape(rom, system_id)
        if scraped_box:
            destination: Path = box_dir / f"{rom.name}.png"
            self.save_file_to_disk(scraped_box, destination)
        if scraped_preview:
            destination: Path = preview_dir / f"{rom.name}.png"
            self.save_file_to_disk(scraped_preview, destination)
        if scraped_synopsis:
            destination: Path = synopsis_dir / f"{rom.name}.txt"
            self.save_file_to_disk(scraped_synopsis.encode("utf-8"), destination)
        return scraped_box, scraped_preview, scraped_synopsis, rom.name

    def load_roms(self) -> None:
        global selected_position, current_window, roms_selected_position, skip_input_check, selected_system

        exit_menu = False
        roms_list = self.get_roms(selected_system)
        if not roms_list:
            self.gui.draw_log(f"No roms found in {selected_system}...")
            self.gui.draw_paint()
            time.sleep(self.LOG_WAIT)
            self.gui.draw_clear()
            exit_menu = True

        system = self.systems_mapping.get(selected_system)
        if not system:
            self.gui.draw_log("System is unknown...")
            self.gui.draw_paint()
            time.sleep(self.LOG_WAIT)
            self.gui.draw_clear()
            exit_menu = True

        box_dir = Path(system["box"])
        preview_dir = Path(system["preview"])
        synopsis_dir = Path(system["synopsis"])
        system_id = system["id"]

        if self.box_enabled and not box_dir.exists():
            box_dir.mkdir(parents=True, exist_ok=True)
            roms_without_box: List[Rom] = roms_list
        elif self.box_enabled:
            box_files = get_image_files_without_extension(box_dir)
            roms_without_box = [rom for rom in roms_list if rom.name not in box_files]
        else:
            roms_without_box = []

        if self.preview_enabled and not preview_dir.exists():
            preview_dir.mkdir(parents=True, exist_ok=True)
            roms_without_preview: List[Rom] = roms_list
        elif self.preview_enabled:
            preview_files = get_image_files_without_extension(preview_dir)
            roms_without_preview = [
                rom for rom in roms_list if rom.name not in preview_files
            ]
        else:
            roms_without_preview = []

        if self.synopsis_enabled and not synopsis_dir.exists():
            synopsis_dir.mkdir(parents=True, exist_ok=True)
            roms_without_synopsis: List[Rom] = roms_list
        elif self.synopsis_enabled:
            synopsis_files = get_txt_files_without_extension(synopsis_dir)
            roms_without_synopsis = [
                rom for rom in roms_list if rom.name not in synopsis_files
            ]
        else:
            roms_without_synopsis = []

        roms_to_scrape = sorted(
            list(set(roms_without_box + roms_without_preview + roms_without_synopsis)),
            key=lambda rom: rom.name,
        )

        if len(roms_to_scrape) < 1:
            current_window = "emulators"
            selected_system = ""
            self.gui.draw_log("No roms with missing media found...")
            self.gui.draw_paint()
            time.sleep(self.LOG_WAIT)
            self.gui.draw_clear()
            exit_menu = True

        if input.key_pressed("B"):
            exit_menu = True
        elif input.key_pressed("A"):
            self.gui.draw_log("Scraping...")
            self.gui.draw_paint()
            rom = roms_to_scrape[roms_selected_position]
            scraped_box, scraped_preview, scraped_synopsis, _ = self.process_rom(
                rom, system_id, box_dir, preview_dir, synopsis_dir
            )

            if not scraped_box and not scraped_preview and not scraped_synopsis:
                self.gui.draw_log("Scraping failed!")
                logger.log_error(f"Failed to get screenshot for {rom.name}")
            else:
                self.gui.draw_log("Scraping completed!")
            self.gui.draw_paint()
            time.sleep(self.LOG_WAIT)
            exit_menu = True
        elif input.key_pressed("START"):
            progress: int = 0
            success: int = 0
            failure: int = 0
            self.gui.draw_log(f"Scraping {progress} of {len(roms_to_scrape)}")
            self.gui.draw_paint()
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                logger.log_debug(f"Available threads: {self.threads}")
                futures = {
                    executor.submit(
                        self.process_rom,
                        rom,
                        system_id,
                        box_dir,
                        preview_dir,
                        synopsis_dir,
                    ): rom
                    for rom in roms_to_scrape
                }
                for future in concurrent.futures.as_completed(futures):
                    scraped_box, scraped_preview, scraped_synopsis, rom_name = (
                        future.result()
                    )
                    if scraped_box or scraped_preview or scraped_synopsis:
                        success += 1
                    else:
                        logger.log_error(f"Failed to get screenshot for {rom_name}")
                        failure += 1
                    progress += 1
                    self.gui.draw_log(f"Scraping {progress} of {len(roms_to_scrape)}")
                    self.gui.draw_paint()
            self.gui.draw_log(
                f"Scraping completed! Success: {success} Errors: {failure}"
            )
            self.gui.draw_paint()
            time.sleep(self.LOG_WAIT)
            exit_menu = True
        elif input.key_pressed("DY"):
            if input.current_value == 1:
                if roms_selected_position < len(roms_to_scrape) - 1:
                    roms_selected_position += 1
            elif input.current_value == -1:
                if roms_selected_position > 0:
                    roms_selected_position -= 1
        elif input.key_pressed("L1"):
            if roms_selected_position > 0:
                roms_selected_position = max(0, roms_selected_position - max_elem)
        elif input.key_pressed("R1"):
            if roms_selected_position < len(roms_list) - 1:
                roms_selected_position = min(
                    len(roms_list) - 1, roms_selected_position + max_elem
                )
        elif input.key_pressed("L2"):
            if roms_selected_position > 0:
                roms_selected_position = max(0, roms_selected_position - 100)
        elif input.key_pressed("R2"):
            if roms_selected_position < len(roms_list) - 1:
                roms_selected_position = min(
                    len(roms_list) - 1, roms_selected_position + 100
                )

        if exit_menu:
            current_window = "emulators"
            selected_system = ""
            self.gui.draw_clear()
            roms_selected_position = 0
            skip_input_check = True
            return

        self.gui.draw_clear()

        self.gui.draw_rectangle_r([10, 40, 630, 440], 15)

        rom_text = f"{selected_system} - Total Roms: {len(roms_list)}"

        missing_parts = []
        if self.box_enabled:
            missing_parts.append(f"No box: {len(roms_without_box)}")
        if self.preview_enabled:
            missing_parts.append(f"No preview: {len(roms_without_preview)}")
        if self.synopsis_enabled:
            missing_parts.append(f"No text: {len(roms_without_synopsis)}")

        missing_text = " / ".join(missing_parts)

        self.gui.draw_text((90, 10), rom_text, anchor="mm")
        self.gui.draw_text((500, 10), missing_text, anchor="mm")

        start_idx = int(roms_selected_position / max_elem) * max_elem
        end_idx = start_idx + max_elem
        for i, rom in enumerate(roms_to_scrape[start_idx:end_idx]):
            already_scraped = [
                flag
                for flag, condition in [
                    ("Box", self.box_enabled and rom not in roms_without_box),
                    (
                        "Preview",
                        self.preview_enabled and rom not in roms_without_preview,
                    ),
                    (
                        "Text",
                        self.synopsis_enabled and rom not in roms_without_synopsis,
                    ),
                ]
                if condition
            ]

            already_scraped_text = "/".join(already_scraped)
            max_length = 48
            base_entry_text = (
                rom.name[:max_length] + "..."
                if len(rom.name) > max_length
                else rom.name
            )

            self.row_list(
                base_entry_text,
                (20, 50 + (i * 35)),
                600,
                i == (roms_selected_position % max_elem),
            )

            if already_scraped_text:
                self.row_list(
                    already_scraped_text,
                    (500, 50 + (i * 35)),
                    50,
                    i == (roms_selected_position % max_elem),
                )
        self.button_rectangle((30, 450), "Start", "All")
        self.button_circle((170, 450), "A", "Download")
        self.button_circle((300, 450), "B", "Back")
        self.button_circle((480, 450), "M", "Exit")

        self.gui.draw_paint()

    def row_list(
        self,
        text: str,
        pos: tuple[int, int],
        width: int,
        selected: bool,
        image_path: str = None,
    ) -> None:
        self.gui.draw_rectangle_r(
            [pos[0], pos[1], pos[0] + width, pos[1] + 32],
            5,
            fill=(
                self.gui.COLOR_PRIMARY if selected else self.gui.COLOR_SECONDARY_LIGHT
            ),
        )

        text_offset_x = pos[0] + 5
        if image_path:
            try:
                image = Image.open(image_path)
                image_width, image_height = image.size
                aspect_ratio = image_width / image_height

                new_width = min(150, image_width)
                new_height = new_width / aspect_ratio

                if new_height < 50:
                    new_height = 50
                    new_width = new_height * aspect_ratio

                self.gui.draw_image(
                    (pos[0] + width - 30, pos[1] + 5),
                    image,
                    new_width,
                    new_height,
                )

            except Exception as e:
                logger.log_error(f"Error loading image from {image_path}: {e}")

        self.gui.draw_text((text_offset_x, pos[1] + 5), text)

    def button_circle(self, pos: tuple[int, int], button: str, text: str) -> None:
        self.gui.draw_circle(pos, 25)
        self.gui.draw_text((pos[0] + 12, pos[1] + 12), button, anchor="mm")
        self.gui.draw_text((pos[0] + 30, pos[1] + 12), text, font=13, anchor="lm")

    def button_rectangle(self, pos: tuple[int, int], button: str, text: str) -> None:
        self.gui.draw_rectangle_r(
            (pos[0], pos[1], pos[0] + 60, pos[1] + 25),
            5,
            fill=self.gui.COLOR_SECONDARY_LIGHT,
        )
        self.gui.draw_text((pos[0] + 30, pos[1] + 12), button, anchor="mm")
        self.gui.draw_text((pos[0] + 65, pos[1] + 12), text, font=13, anchor="lm")


if __name__ == "__main__":
    app = App()
    app.start(f"{os.getcwd()}/config.json")

    while True:
        app.update()
