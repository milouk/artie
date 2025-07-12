import concurrent.futures
import json
import logging
import os
import sys
import threading
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

VERSION = "1.0.7"

selected_position = 0
roms_selected_position = 0
selected_system = ""
current_window = "emulators"
max_elem = 11
skip_input_check = False
ping = time.time()

roms_list = None
available_systems = None
roms_to_scrape = None

roms_without_box = None
roms_without_preview = None
roms_without_synopsis = None

preview_lock = threading.Lock()
previews = set()
current_preview = ""


class Rom:
    def __init__(self, name, filename, path):
        self.name = name
        self.filename = filename
        self.path = path


class App:
    LOG_WAIT = 2

    def __init__(self):
        self.input_thread = None
        self.colors = None
        self.dev_id = None
        self.dev_password = None
        self.config = {}
        self.systems_mapping = {}
        self.roms_path = ""
        self.systems_logo_path = ""
        self.content = {}
        self.box_enabled = True
        self.preview_enabled = True
        self.synopsis_enabled = True
        self.meta_enabled = True
        self.threads = 1
        self.username = ""
        self.password = ""
        self.gui = GUI()
        self.sub_dirs = False

    def update_systems_mapping(self):
        self.systems_mapping = {}

        for system in self.config["screenscraper"]["systems"]:
            system_dir = system["dir"].lower()

            # Check for exact match first
            if os.path.isdir(os.path.join(self.roms_path, system_dir)):
                self.systems_mapping[system_dir] = system
            else:
                # Check for partial matches using identifiers and excludes
                for dir_name in os.listdir(self.roms_path):
                    dir_lower = dir_name.lower()

                    if any(identifier.lower() in dir_lower for identifier in system["identifiers"]) and \
                            all(exclude.lower() not in dir_lower for exclude in system["excludes"]):
                        logger.log_info(system)
                        self.systems_mapping[dir_lower] = system
                        break
                    else:
                        self.systems_mapping[system_dir] = system
        return self.systems_mapping

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
        if not Path(self.roms_path).exists() or not any(Path(self.roms_path).iterdir()):
            self.roms_path = self.config.get("roms_alt")
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
        self.meta_enabled = self.content["synopsis"]["meta"]

        self.sub_dirs = self.config.get("sub_dirs")
        self.get_user_threads()

        self.update_systems_mapping()

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
        self.setup_logging()
        logger.log_debug(f"Artie Scraper v{VERSION}")
        self.load_config(config_file)
        self.gui.draw_start()
        self.gui.screen_reset()
        main_gui = self.gui.create_image()
        self.gui.draw_active(main_gui)
        self.load_emulators()
        self.input_thread = input.start_input_thread()

    def update(self) -> None:
        global skip_input_check, current_window, ping
        if skip_input_check:
            input.reset_input()
            skip_input_check = False

        if input.key_pressed(input.MENU):
            self.gui.draw_end()
            input.should_exit = True
            self.input_thread.join()
            sys.exit()

        if current_window == "emulators":
            self.load_emulators()
        elif current_window == "roms":
            self.load_roms()
        dt = time.time()-ping
        if dt < 0.05:
            time.sleep(0.05-dt)
        ping = time.time()

    def get_available_systems(self) -> List[str]:
        out = [
            d.lower()
            for d in os.listdir(self.roms_path)
            if Path(self.roms_path, d).is_dir()
        ]
        return sorted(
            [system for system in out if system in self.systems_mapping]
        )

    def get_roms(self, system: str) -> list[Rom]:
        roms = []
        system_path = Path(self.roms_path) / system

        for root, dirs, files in os.walk(system_path):
            if self.sub_dirs:
                dirs[:] = [d for d in dirs if not d.startswith(".")]
            else:
                dirs[:] = []

            for file in files:
                file_path = Path(root) / file
                if file.startswith("."):
                    continue
                if file_path.is_file() and self.is_valid_rom(file):
                    logger.log_info(file_path)
                    name = file_path.stem
                    rom = Rom(filename=file, name=name, path=file_path)
                    roms.append(rom)
        return roms

    @staticmethod
    def delete_files_in_directory(filenames, directory_path):
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
        global selected_position, selected_system, current_window, skip_input_check, available_systems, \
            roms_list, roms_to_scrape

        self.gui.draw_clear()
        self.gui.draw_rectangle_r([10, 40, 630, 440], 15)
        self.gui.draw_text((320, 20), f"Artie Scraper v{VERSION}", anchor="mm")

        if available_systems is None:
            if not Path(self.roms_path).exists() or not any(Path(self.roms_path).iterdir()):
                self.gui.draw_log("Wrong Roms path, check config.json")
                self.gui.draw_paint()
                time.sleep(self.LOG_WAIT)
                sys.exit()
            available_systems = self.get_available_systems()

        if available_systems:
            if input.key_pressed(input.DY, 1):
                if selected_position < len(available_systems) - 1:
                    selected_position += 1
                else:
                    selected_position = 0
            elif input.key_pressed(input.DY, -1):
                if selected_position > 0:
                    selected_position -= 1
                else:
                    selected_position = len(available_systems) - 1
            elif input.key_pressed(input.A):
                selected_system = available_systems[selected_position]
                roms_list = None
                roms_to_scrape = None
                current_window = "roms"
                skip_input_check = True
                return
            elif input.key_pressed(input.X):
                selected_system = available_systems[selected_position]
                self.delete_system_media()
                self.gui.draw_log(f"Deleting all existing {selected_system} media...")
                self.gui.draw_paint()
                skip_input_check = True
                time.sleep(self.LOG_WAIT)
                return
            elif input.key_pressed(input.L1):
                if selected_position > 0:
                    selected_position = max(0, selected_position - max_elem)
            elif input.key_pressed(input.R1):
                if selected_position < len(available_systems) - 1:
                    selected_position = min(
                        len(available_systems) - 1, selected_position + max_elem
                    )
            elif input.key_pressed(input.L2):
                if selected_position > 0:
                    selected_position = max(0, selected_position - 100)
            elif input.key_pressed(input.R2):
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

    @staticmethod
    def is_valid_rom(rom):
        invalid_extensions = {
            ".cue",
            ".jpg",
            ".png",
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

    @staticmethod
    def save_file_to_disk(data, destination):
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
                    scraped_synopsis = fetch_synopsis(game, content, self.meta_enabled)
        except Exception as e:
            logger.log_error(f"Error scraping {rom.name}: {e}")

        return scraped_box, scraped_preview, scraped_synopsis

    def process_rom(self, rom, system_id, box_dir, preview_dir, synopsis_dir):
        scraped_box, scraped_preview, scraped_synopsis = self.scrape(rom, system_id)
        # I've noticed in some cases a scrape fails but succeeds on the second try, the scrapper.fr might be
        # overwhelmed, let's give it a short break and try again.
        if (self.box_enabled and scraped_box is None) or \
                (self.preview_enabled and scraped_preview is None) or \
                (self.synopsis_enabled and scraped_synopsis is None):
            time.sleep(0.5)
            scraped_box, scraped_preview, scraped_synopsis = self.scrape(rom, system_id)

        if scraped_box:
            destination: Path = box_dir / f"{rom.name}.png"
            self.save_file_to_disk(scraped_box, destination)
            with preview_lock:
                previews.add(str(destination))
        if scraped_preview:
            destination: Path = preview_dir / f"{rom.name}.png"
            self.save_file_to_disk(scraped_preview, destination)
        if scraped_synopsis:
            destination: Path = synopsis_dir / f"{rom.name}.txt"
            self.save_file_to_disk(scraped_synopsis.encode("utf-8"), destination)
        return scraped_box, scraped_preview, scraped_synopsis, rom.name

    def load_roms(self) -> None:
        global selected_position, current_window, roms_selected_position, skip_input_check, current_preview, \
            selected_system, roms_list, roms_to_scrape, roms_without_box, roms_without_preview, roms_without_synopsis

        exit_menu = False

        system = self.systems_mapping.get(selected_system)
        if not system:
            self.gui.draw_log("System is unknown...")
            self.gui.draw_paint()
            time.sleep(self.LOG_WAIT)
            self.gui.draw_clear()
            exit_menu = True

        if roms_list is None:
            roms_list = self.get_roms(selected_system)
            if not roms_list:
                self.gui.draw_log(f"No roms found in {selected_system}...")
                self.gui.draw_paint()
                time.sleep(self.LOG_WAIT)
                self.gui.draw_clear()
                exit_menu = True

        box_dir = Path(system["box"])
        preview_dir = Path(system["preview"])
        synopsis_dir = Path(system["synopsis"])
        system_id = system["id"]

        if roms_to_scrape is None:
            roms_to_scrape = self.list_roms_with_missing_media(box_dir, preview_dir, roms_list, synopsis_dir)

        if len(roms_to_scrape) < 1:
            current_window = "emulators"
            selected_system = ""
            self.gui.draw_log("No roms with missing media found...")
            self.gui.draw_paint()
            time.sleep(self.LOG_WAIT)
            self.gui.draw_clear()
            exit_menu = True

        if input.key_pressed(input.B):
            roms_list = None
            roms_to_scrape = None
            exit_menu = True
        elif input.key_pressed(input.A):
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
                with preview_lock:
                    if len(previews) > 0:
                        current_preview = previews.pop()
                    previews.clear()
                self.gui.draw_preview("Scraping completed!", current_preview)
            self.gui.draw_paint()
            current_preview = ""
            time.sleep(self.LOG_WAIT)
            if roms_to_scrape == 1:
                exit_menu = True
            if roms_selected_position < 0:
                roms_selected_position -= 1
            roms_to_scrape = self.list_roms_with_missing_media(box_dir, preview_dir, roms_list, synopsis_dir)
            input.reset_input()
        elif input.key_pressed(input.START):
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
                    with preview_lock:
                        if len(previews) > 0:
                            current_preview = previews.pop()
                    self.gui.draw_preview(f"Scraping {progress} of {len(roms_to_scrape)}", current_preview)
                    self.gui.draw_paint()
            with preview_lock:
                self.gui.draw_preview(f"Scraping completed! Success: {success} Errors: {failure}", current_preview)
                previews.clear()
            roms_to_scrape = None
            self.gui.draw_paint()
            current_preview = ""
            time.sleep(self.LOG_WAIT)
            exit_menu = True
        elif input.key_pressed(input.DY, 1):
            if roms_selected_position < len(roms_to_scrape) - 1:
                roms_selected_position += 1
            else:
                roms_selected_position = 0
        elif input.key_pressed(input.DY, -1):
            if roms_selected_position > 0:
                roms_selected_position -= 1
            else:
                roms_selected_position = len(roms_to_scrape) - 1
        elif input.key_pressed(input.L1):
            if roms_selected_position > 0:
                roms_selected_position = max(0, roms_selected_position - max_elem)
        elif input.key_pressed(input.R1):
            if roms_selected_position < len(roms_list) - 1:
                roms_selected_position = min(
                    len(roms_list) - 1, roms_selected_position + max_elem
                )
        elif input.key_pressed(input.L2):
            if roms_selected_position > 0:
                roms_selected_position = max(0, roms_selected_position - 100)
        elif input.key_pressed(input.R2):
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

        self.gui.draw_text((120, 10), rom_text, anchor="mm")
        self.gui.draw_text((480, 10), missing_text, anchor="mm")

        start_idx = (roms_selected_position // max_elem) * max_elem
        end_idx = start_idx + max_elem
        max_length = 48

        for i, rom in enumerate(roms_to_scrape[start_idx:end_idx]):
            # Use set membership for O(1) checks
            already_scraped = []
            if self.box_enabled and rom not in roms_without_box:
                already_scraped.append("Box")
            if self.preview_enabled and rom not in roms_without_preview:
                already_scraped.append("Preview")
            if self.synopsis_enabled and rom not in roms_without_synopsis:
                already_scraped.append("Text")
            already_scraped_text = "/".join(already_scraped)

            base_entry_text = (
                rom.name[:max_length] + "..." if len(rom.name) > max_length else rom.name
            )
            y_pos = 50 + (i * 35)
            is_selected = i == (roms_selected_position % max_elem)

            self.row_list(base_entry_text, (20, y_pos), 600, is_selected)
            if already_scraped_text:
                self.row_list(already_scraped_text, (500, y_pos), 50, is_selected)

        self.button_rectangle((30, 450), "Start", "All")
        self.button_circle((170, 450), "A", "Download")
        self.button_circle((300, 450), "B", "Back")
        self.button_circle((480, 450), "M", "Exit")

        self.gui.draw_paint()

    def list_roms_with_missing_media(self, box_dir, preview_dir, roms_list, synopsis_dir):
        global roms_without_box, roms_without_preview, roms_without_synopsis
        if not box_dir.exists():
            box_dir.mkdir(parents=True, exist_ok=True)
            roms_without_box = set(roms_list) if self.box_enabled else set()
        else:
            box_files = get_image_files_without_extension(box_dir)
            roms_without_box = set([rom for rom in roms_list if rom.name not in box_files]) \
                if self.box_enabled else set()

        if not preview_dir.exists():
            preview_dir.mkdir(parents=True, exist_ok=True)
            roms_without_preview = set(roms_list) if self.preview_enabled else set()
        else:
            preview_files = get_image_files_without_extension(preview_dir)
            roms_without_preview = set([rom for rom in roms_list if rom.name not in preview_files]) \
                if self.preview_enabled else set()

        if not synopsis_dir.exists():
            synopsis_dir.mkdir(parents=True, exist_ok=True)
            roms_without_synopsis = set(roms_list) if self.synopsis_enabled else set()
        else:
            synopsis_files = get_txt_files_without_extension(synopsis_dir)
            roms_without_synopsis = set([rom for rom in roms_list if rom.name not in synopsis_files]) \
                if self.synopsis_enabled else set()
        return sorted(
            list(roms_without_box | roms_without_preview | roms_without_synopsis),
            key=lambda rom: rom.name,
        )

    def row_list(
        self,
        text: str,
        pos: tuple[int, int],
        width: int,
        selected: bool,
        image_path: str = None,
    ) -> None:
        if selected:
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
