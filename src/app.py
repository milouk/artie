import json
import os
import sys
import time
from pathlib import Path
from typing import List

import graphic as gr
import input
from PIL import Image
from scraper import (
    check_destination,
    download_media,
    find_game,
    get_image_files_without_extension,
)

selected_position = 0
roms_selected_position = 0
selected_system = ""
current_window = "emulators"
max_elem = 11
skip_input_check = False
scraping = False


class Rom:
    def __init__(self, name, filename):
        self.name = name
        self.filename = filename


class App:
    def __init__(self):
        self.config = {}
        self.systems_mapping = {}
        self.roms_path = ""
        self.systems_logo_path = ""
        self.media = {}
        self.threads = 1
        self.username = ""
        self.password = ""

    def load_config(self, config_file):
        with open(config_file, "r") as file:
            file_contents = file.read()

        self.config = json.loads(file_contents)
        self.roms_path = self.config.get("roms")
        self.systems_logo_path = self.config.get("logos")
        self.dev_id = self.config.get("screenscraper").get("devid")
        self.dev_password = self.config.get("screenscraper").get("devpassword")
        self.username = self.config.get("screenscraper").get("username")
        self.password = self.config.get("screenscraper").get("password")
        self.media = self.config.get("screenscraper").get("media")
        self.threads = self.config.get("threads")
        for system in self.config["screenscraper"]["systems"]:
            self.systems_mapping[system["dir"]] = system

    def start(self, config_file: str) -> None:
        print("Starting Artie...")
        self.load_config(config_file)
        self.load_emulators()

    def update(self) -> None:
        global current_window, selected_position, skip_input_check

        if skip_input_check:
            input.reset_input()
            skip_input_check = False
        else:
            input.check_input()

        if input.key_pressed("MENUF"):
            gr.draw_end()
            print("Exiting Artie...")
            sys.exit()

        if current_window == "emulators":
            self.load_emulators()
        elif current_window == "roms":
            self.load_roms()
        else:
            self.load_emulators()

    def get_available_systems(self) -> list[str]:
        all_systems = list(self.systems_mapping.keys())
        available_systems = [
            d.upper()
            for d in os.listdir(self.roms_path)
            if os.path.isdir(os.path.join(self.roms_path, d))
        ]
        filtered_systems = [
            system for system in available_systems if system in all_systems
        ]
        return filtered_systems

    def get_roms(self, system: str) -> list[Rom]:
        roms = []
        system_path = Path(self.roms_path) / system

        for file in os.listdir(system_path):
            file_path = Path(system_path) / file
            if file.startswith("."):
                continue
            if file_path.is_file() and self.is_valid_rom(file):
                name = file_path.stem
                rom = Rom(filename=file, name=name)
                roms.append(rom)

        return roms

    def load_emulators(self) -> None:
        global selected_position, selected_system, current_window, skip_input_check

        gr.draw_clear()
        gr.draw_rectangle_r([10, 40, 630, 440], 15, fill=gr.COLOR_GRAY_D2, outline=None)
        gr.draw_text((320, 20), "Artie Scraper", anchor="mm")

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
                gr.draw_log(
                    "Checking existing media...",
                    fill=gr.COLOR_BLUE,
                    outline=gr.COLOR_BLUE_D1,
                )
                gr.draw_paint()
                skip_input_check = True
                return

        if len(available_systems) >= 1:
            start_idx = int(selected_position / max_elem) * max_elem
            end_idx = start_idx + max_elem
            for i, system in enumerate(available_systems[start_idx:end_idx]):
                logo = f"{self.systems_logo_path}/{system}.png"
                self.row_list(
                    system,
                    (20, 50 + (i * 35)),
                    600,
                    i == (selected_position % max_elem),
                    # logo,
                )

            self.button_circle((30, 450), "A", "Select")
        else:
            gr.draw_text(
                (320, 240), f"No Emulators found in {self.roms_path}", anchor="mm"
            )

        self.button_circle((133, 450), "M", "Exit")

        gr.draw_paint()

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
        }
        return os.path.splitext(rom)[1] not in invalid_extensions

    def save_to_disk(self, rom, scraped_media, art_folder):
        img_path: Path = art_folder / f"{rom.name}.png"
        check_destination(img_path)
        img_path.write_bytes(scraped_media)
        gr.draw_log("Scraping completed!", fill=gr.COLOR_BLUE, outline=gr.COLOR_BLUE_D1)
        return True

    def scrape(self, rom, system_path, system_id):
        game = find_game(
            system_id,
            system_path / rom.filename,
            self.dev_id,
            self.dev_password,
            self.username,
            self.password,
        )
        if game:
            medias = game["response"]["jeu"]["medias"]
            media = download_media(medias, self.media)
            if media:
                return media

    def load_roms(self) -> None:
        global selected_position, current_window, roms_selected_position, skip_input_check, selected_system

        exit_menu = False
        roms_list = self.get_roms(selected_system)
        system_path = Path(self.roms_path) / selected_system
        system = self.systems_mapping.get(selected_system)
        if not system:
            gr.draw_log(
                "System is unknown...",
                fill=gr.COLOR_BLUE,
                outline=gr.COLOR_BLUE_D1,
            )
            gr.draw_paint()
            time.sleep(2)
            gr.draw_clear()
            exit_menu = True

        art_folder = Path(system["art"])
        system_id = system["id"]

        if not art_folder.exists():
            art_folder.mkdir()
            imgs_files: List[str] = []
        else:
            imgs_files = get_image_files_without_extension(art_folder)

        roms_without_image = [rom for rom in roms_list if rom.name not in imgs_files]

        if len(roms_without_image) < 1:
            current_window = "emulators"
            selected_system = ""
            gr.draw_log(
                "No roms missing media found...",
                fill=gr.COLOR_BLUE,
                outline=gr.COLOR_BLUE_D1,
            )
            gr.draw_paint()
            time.sleep(2)
            gr.draw_clear()
            exit_menu = True

        if input.key_pressed("B"):
            exit_menu = True
        elif input.key_pressed("A"):
            gr.draw_log("Scraping...", fill=gr.COLOR_BLUE, outline=gr.COLOR_BLUE_D1)
            gr.draw_paint()
            rom = roms_without_image[roms_selected_position]
            scraped_media = self.scrape(rom, system_path, system_id)
            if scraped_media:
                self.save_to_disk(rom, scraped_media, art_folder)
            else:
                gr.draw_log(
                    "Scraping failed!", fill=gr.COLOR_BLUE, outline=gr.COLOR_BLUE_D1
                )
                print(f"Failed to get screenshot for {rom.name}")
            gr.draw_paint()
            time.sleep(3)
            exit_menu = True
        elif input.key_pressed("START"):
            progress: int = 0
            success: int = 0
            failure: int = 0
            gr.draw_log(
                f"Scraping {progress} of {len(roms_without_image)}",
                fill=gr.COLOR_BLUE,
                outline=gr.COLOR_BLUE_D1,
            )
            gr.draw_paint()
            for rom in roms_without_image:
                if rom.name not in imgs_files:
                    scraped_media = self.scrape(rom, system_path, system_id)
                    if scraped_media:
                        self.save_to_disk(rom, scraped_media, art_folder)
                    else:
                        gr.draw_log(
                            "Scraping failed!",
                            fill=gr.COLOR_BLUE,
                            outline=gr.COLOR_BLUE_D1,
                        )
                        print(f"Failed to get screenshot for {rom.name}")
                        failure += 1
                    progress += 1
                    gr.draw_log(
                        f"Scraping {progress} of {len(roms_without_image)}",
                        fill=gr.COLOR_BLUE,
                        outline=gr.COLOR_BLUE_D1,
                    )
                    gr.draw_paint()
            gr.draw_log(
                f"Scraping completed! Success: {success} Errors: {failure}",
                fill=gr.COLOR_BLUE,
                outline=gr.COLOR_BLUE_D1,
                width=800,
            )
            gr.draw_paint()
            time.sleep(4)
            exit_menu = True
        elif input.key_pressed("DY"):
            if input.current_value == 1:
                if roms_selected_position < len(roms_list) - 1:
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
            gr.draw_clear()
            roms_selected_position = 0
            skip_input_check = True
            return

        gr.draw_clear()

        gr.draw_rectangle_r([10, 40, 630, 440], 15, fill=gr.COLOR_GRAY_D2, outline=None)
        gr.draw_text(
            (320, 10),
            f"{selected_system} - Roms: {len(roms_list)} Missing media: {len(roms_without_image)}",
            anchor="mm",
        )

        start_idx = int(roms_selected_position / max_elem) * max_elem
        end_idx = start_idx + max_elem
        for i, rom in enumerate(roms_without_image[start_idx:end_idx]):
            self.row_list(
                rom.name[:48] + "..." if len(rom.name) > 50 else rom.name,
                (20, 50 + (i * 35)),
                600,
                i == (roms_selected_position % max_elem),
            )

        self.button_rectangle((30, 450), "Start", "All")
        self.button_circle((170, 450), "A", "Download")
        self.button_circle((300, 450), "B", "Back")
        self.button_circle((480, 450), "M", "Exit")

        gr.draw_paint()

    def row_list(
        self,
        text: str,
        pos: tuple[int, int],
        width: int,
        selected: bool,
        image_path: str = None,
    ) -> None:
        gr.draw_rectangle_r(
            [pos[0], pos[1], pos[0] + width, pos[1] + 32],
            5,
            fill=(gr.COLOR_BLUE if selected else gr.COLOR_GRAY_L1),
        )

        text_offset_x = pos[0] + 5
        if image_path:
            try:
                image = Image.open(image_path)
                image_width, image_height = image.size
                # gr.draw_image((pos[0] + 5, pos[1] + (32 - image_height) // 2), image)
                text_offset_x += image_width + 5
            except Exception as e:
                print(f"Error loading image from {image_path}: {e}")

        # Draw the text
        gr.draw_text((text_offset_x, pos[1] + 5), text)

    def button_circle(self, pos: tuple[int, int], button: str, text: str) -> None:
        gr.draw_circle(pos, 25, fill=gr.COLOR_BLUE_D1)
        gr.draw_text((pos[0] + 12, pos[1] + 12), button, anchor="mm")
        gr.draw_text((pos[0] + 30, pos[1] + 12), text, font=13, anchor="lm")

    def button_rectangle(self, pos: tuple[int, int], button: str, text: str) -> None:
        gr.draw_rectangle_r(
            (pos[0], pos[1], pos[0] + 60, pos[1] + 25), 5, fill=gr.COLOR_GRAY_L1
        )
        gr.draw_text((pos[0] + 30, pos[1] + 12), button, anchor="mm")
        gr.draw_text((pos[0] + 65, pos[1] + 12), text, font=13, anchor="lm")


if __name__ == "__main__":
    app = App()
    app.start(f"{os.getcwd()}/config.json")

    while True:
        app.update()
