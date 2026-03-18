"""Settings screen and virtual keyboard for Artie Scraper."""

import json
from typing import List, Optional, Tuple

import input as inp
from logger import LoggerSingleton as logger


# ---------------------------------------------------------------------------
# Settings definitions
# ---------------------------------------------------------------------------

# Each tuple: (section, key, label, widget_type, extra_kwargs)
# Keys are flat — they map directly to settings.json top-level keys.
# Preset region orderings keyed by primary region
REGION_PRESETS = {
    "us": "us,eu,jp,br,ss,ame,wor",
    "eu": "eu,us,jp,br,ss,ame,wor",
    "jp": "jp,us,eu,br,ss,ame,wor",
    "br": "br,us,eu,jp,ss,ame,wor",
    "wor": "wor,us,eu,jp,br,ss,ame",
}

SETTINGS_DEFS: List[Tuple[str, str, str, str, dict]] = [
    ("Account", "username", "Username", "text", {}),
    ("Account", "password", "Password", "password", {}),
    ("Scraping", "threads", "Threads", "number", {"min": 1, "max": 20}),
    ("Scraping", "show_scraped_roms", "Show All ROMs", "toggle", {}),
    (
        "Scraping",
        "regions",
        "Region Priority",
        "choice",
        {"options": list(REGION_PRESETS.keys())},
    ),
    ("Media", "box_enabled", "Box Art", "toggle", {}),
    (
        "Media",
        "box_type",
        "Box Type",
        "choice",
        {"options": ["mixrbv2", "mixrbv1", "box-2D", "box-3D"]},
    ),
    ("Media", "box_mask", "Box Mask", "toggle", {}),
    ("Media", "box_mask_path", "Box Mask Path", "text", {}),
    ("Media", "preview_enabled", "Preview", "toggle", {}),
    (
        "Media",
        "preview_type",
        "Preview Type",
        "choice",
        {"options": ["ss", "sstitle", "fanart"]},
    ),
    ("Media", "preview_mask", "Preview Mask", "toggle", {}),
    ("Media", "preview_mask_path", "Preview Mask Path", "text", {}),
    ("Media", "synopsis_enabled", "Synopsis", "toggle", {}),
    ("Media", "video_enabled", "Video", "toggle", {}),
    ("Display", "show_logos", "Show Logos", "toggle", {}),
    (
        "Display",
        "theme",
        "Theme",
        "choice",
        {"options": ["dark", "light"]},
    ),
    ("Advanced", "offline_mode", "Offline Mode", "toggle", {}),
    (
        "Advanced",
        "log_level",
        "Log Level",
        "choice",
        {"options": ["debug", "info", "warning", "error"]},
    ),
]


# ---------------------------------------------------------------------------
# Virtual Keyboard
# ---------------------------------------------------------------------------


class VirtualKeyboard:
    """On-screen keyboard for gamepad text input."""

    LAYOUTS = {
        "lower": [
            list("abcdefghij"),
            list("klmnopqrst"),
            list("uvwxyz0123"),
            list("456789.@_-"),
        ],
        "upper": [
            list("ABCDEFGHIJ"),
            list("KLMNOPQRST"),
            list("UVWXYZ0123"),
            list("456789.@_-"),
        ],
        "symbol": [
            list("!@#$%^&*()"),
            list("-_=+[]{}\\|"),
            list(";:'\",.<>/?"),
            list("~`      $ "),
        ],
    }

    # Action row appended to every layout
    _ACTION_ROW = ["SHIFT", "SPACE", "BKSP", "OK"]

    def __init__(self, gui, title: str = "", initial: str = "", masked: bool = False):
        self.gui = gui
        self.title = title
        self.chars: List[str] = list(initial)
        self.masked = masked
        self.layout = "lower"
        self.row = 0
        self.col = 0

    # -- public API --

    def run(self) -> Optional[str]:
        """Show keyboard. Returns the entered string, or None if cancelled."""
        while True:
            self._render()
            inp.check_input()

            if inp.key_pressed("DY"):
                rows = self._rows()
                if inp.current_value == 1:
                    self.row = min(self.row + 1, len(rows) - 1)
                else:
                    self.row = max(self.row - 1, 0)
                self.col = min(self.col, len(rows[self.row]) - 1)

            elif inp.key_pressed("DX"):
                row_keys = self._rows()[self.row]
                if inp.current_value == 1:
                    self.col = min(self.col + 1, len(row_keys) - 1)
                else:
                    self.col = max(self.col - 1, 0)

            elif inp.key_pressed("A"):
                key = self._rows()[self.row][self.col]
                result = self._handle_key(key)
                if result == "OK":
                    return "".join(self.chars)

            elif inp.key_pressed("B"):
                if self.chars:
                    self.chars.pop()

            elif inp.key_pressed("X"):
                self._cycle_layout()

            elif inp.key_pressed("START"):
                return "".join(self.chars)

            elif inp.key_pressed("Y") or inp.key_pressed("MENUF"):
                return None

    # -- internals --

    def _rows(self) -> List[list]:
        return self.LAYOUTS[self.layout] + [self._ACTION_ROW]

    def _cycle_layout(self) -> None:
        names = list(self.LAYOUTS.keys())
        idx = names.index(self.layout)
        self.layout = names[(idx + 1) % len(names)]

    def _handle_key(self, key: str) -> Optional[str]:
        if key in ("SHIFT",):
            self.layout = "upper" if self.layout == "lower" else "lower"
        elif key == "SPACE":
            self.chars.append(" ")
        elif key == "BKSP":
            if self.chars:
                self.chars.pop()
        elif key == "OK":
            return "OK"
        elif key.strip():
            self.chars.append(key)
        return None

    def _render(self) -> None:
        g = self.gui
        scr = g.create_image()
        g.draw_active(scr)

        # Header
        g.draw_rectangle_r([0, 0, 640, 36], 0, fill=g.COLOR_HEADER_BG)
        g.draw_text((20, 18), self.title, font=18, color=g.COLOR_PRIMARY, anchor="lm")

        # Text input area
        g.draw_rectangle_r([20, 50, 620, 90], 6, fill=g.COLOR_SECONDARY_LIGHT)
        display = "".join(self.chars)
        if self.masked:
            display = "*" * len(display)
        # Truncate from left so cursor stays visible
        font_obj = g.fontFile[18]
        max_w = 570
        while font_obj.size(display + "|")[0] > max_w and display:
            display = display[1:]
        g.draw_text((30, 70), display + "|", font=18, color=g.COLOR_WHITE, anchor="lm")

        # Keyboard grid
        rows = self._rows()
        start_y = 110
        row_h = 55
        for ri, row in enumerate(rows):
            kw = 600 // len(row)
            for ci, key in enumerate(row):
                x = 20 + ci * kw
                y = start_y + ri * row_h
                w = kw - 4
                h = row_h - 8
                selected = ri == self.row and ci == self.col

                is_action = key in ("SHIFT", "SPACE", "BKSP", "OK")
                if selected:
                    bg = g.COLOR_PRIMARY
                elif is_action:
                    bg = g.COLOR_ROW_HOVER
                else:
                    bg = g.COLOR_SECONDARY_LIGHT

                g.draw_rectangle_r([x, y, x + w, y + h], 6, fill=bg)

                label = {
                    "SPACE": "SPC",
                    "BKSP": "DEL",
                    "SHIFT": "SHIFT",
                }.get(key, key)

                fsz = 14 if len(label) <= 2 else 11
                clr = g.COLOR_WHITE if selected else g.COLOR_MUTED
                g.draw_text(
                    (x + w // 2, y + h // 2), label, font=fsz, color=clr, anchor="mm"
                )

        # Controls
        g.draw_line((10, 443), (630, 443), fill=g.COLOR_SECONDARY_LIGHT, width=1)
        y = 453
        _pill(g, (15, y), "A", "Type")
        _pill(g, (110, y), "B", "Del")
        _pill(g, (220, y), "X", "Shift")
        _pill(g, (330, y), "Y", "Cancel")
        _pill(g, (450, y), "ST", "Confirm")

        g.draw_paint()


# ---------------------------------------------------------------------------
# Settings Screen
# ---------------------------------------------------------------------------


class SettingsScreen:
    """Full-screen settings editor."""

    MAX_VISIBLE = 8

    def __init__(self, gui, settings_path: str, settings: dict, max_threads: int = 20):
        self.gui = gui
        self.settings_path = settings_path
        self.settings = settings

        # Build flat list of editable settings with current values
        self.items: List[dict] = []
        prev_section = None
        for section, key, label, wtype, extra in SETTINGS_DEFS:
            # Override thread max with API-reported limit
            if key == "threads":
                extra = {**extra, "max": max_threads}
            value = settings.get(key)
            # Regions: stored as comma string, display as primary region
            if key == "regions" and isinstance(value, str):
                primary = value.split(",")[0].strip() if value else "us"
                if primary not in REGION_PRESETS:
                    primary = "us"
                value = primary
            self.items.append(
                {
                    "section": section,
                    "show_section": section != prev_section,
                    "key": key,
                    "label": label,
                    "type": wtype,
                    "value": value,
                    "original": value,
                    **extra,
                }
            )
            prev_section = section

        self.pos = 0

    @property
    def dirty(self) -> bool:
        return any(i["value"] != i["original"] for i in self.items)

    # -- public API --

    def show(self) -> bool:
        """Run settings screen. Returns True if settings were saved."""
        while True:
            self._render()
            inp.check_input()

            if inp.key_pressed("DY"):
                if inp.current_value == 1 and self.pos < len(self.items) - 1:
                    self.pos += 1
                elif inp.current_value == -1 and self.pos > 0:
                    self.pos -= 1

            elif inp.key_pressed("A") or inp.key_pressed("DX"):
                item = self.items[self.pos]
                if item["type"] == "toggle":
                    item["value"] = not item["value"]

                elif item["type"] == "number" and inp.key_pressed("DX"):
                    self._adjust_number(item, inp.current_value)
                elif item["type"] == "choice" and inp.key_pressed("DX"):
                    self._cycle_choice(item, inp.current_value)
                elif item["type"] in ("text", "password") and inp.key_pressed("A"):
                    self._edit_text(item)

            elif inp.key_pressed("START"):
                self._save()
                return True

            elif inp.key_pressed("B"):
                return False

            elif inp.key_pressed("MENUF"):
                return False

    # -- editing helpers --

    def _adjust_number(self, item: dict, direction: int) -> None:
        lo = item.get("min", 1)
        hi = item.get("max", 99)
        val = item.get("value", lo)
        if not isinstance(val, int):
            val = lo
        item["value"] = max(lo, min(hi, val + direction))

    def _cycle_choice(self, item: dict, direction: int) -> None:
        options = item.get("options", [])
        if not options:
            return
        current = item.get("value")
        try:
            idx = options.index(current)
        except ValueError:
            idx = 0
        item["value"] = options[(idx + direction) % len(options)]

    def _edit_text(self, item: dict) -> None:
        current = item.get("value") or ""
        kb = VirtualKeyboard(
            self.gui,
            title=item["label"],
            initial=str(current),
            masked=item["type"] == "password",
        )
        result = kb.run()
        if result is not None:
            item["value"] = result

    # -- persistence --

    def _save(self) -> None:
        """Write settings to settings.json."""
        try:
            data = {}
            for item in self.items:
                value = item["value"]
                # Regions: expand primary key to full comma string
                if item["key"] == "regions":
                    value = REGION_PRESETS.get(value, REGION_PRESETS["us"])
                data[item["key"]] = value

            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")

            # Update originals so dirty resets
            for item in self.items:
                item["original"] = item["value"]

            logger.log_info("Settings saved to settings.json")

        except Exception as e:
            logger.log_error(f"Failed to save settings: {e}")

    # -- rendering --

    def _render(self) -> None:
        g = self.gui
        scr = g.create_image()
        g.draw_active(scr)

        # Header
        g.draw_rectangle_r([0, 0, 640, 36], 0, fill=g.COLOR_HEADER_BG)
        g.draw_text((20, 18), "SETTINGS", font=18, color=g.COLOR_PRIMARY, anchor="lm")
        if self.dirty:
            g.draw_rectangle_r([160, 8, 250, 28], 10, fill=g.COLOR_PRIMARY_DARK)
            g.draw_text(
                (205, 18), "modified", font=10, color=g.COLOR_WHITE, anchor="mm"
            )

        # Content area
        g.draw_rectangle_r([10, 42, 630, 438], 10, fill=g.COLOR_SECONDARY_DARK)

        # Draw visible items with variable spacing
        page_start = (self.pos // self.MAX_VISIBLE) * self.MAX_VISIBLE
        page_end = page_start + self.MAX_VISIBLE

        cur_y = 50
        for i, item in enumerate(self.items[page_start:page_end]):
            idx = page_start + i
            selected = idx == self.pos
            # Extra space before a new section header
            if item["show_section"]:
                if i > 0:
                    cur_y += 8
                self._draw_section_header(item["section"], cur_y)
                cur_y += 20
            self._draw_setting_row(item, cur_y, selected)
            cur_y += 26

        # Page indicator
        total_pages = max(
            1, (len(self.items) + self.MAX_VISIBLE - 1) // self.MAX_VISIBLE
        )
        current_page = (self.pos // self.MAX_VISIBLE) + 1
        g.draw_text(
            (620, 18),
            f"{current_page}/{total_pages}",
            font=11,
            color=g.COLOR_MUTED,
            anchor="rm",
        )

        # Controls
        g.draw_line((10, 443), (630, 443), fill=g.COLOR_SECONDARY_LIGHT, width=1)
        y = 453
        _pill(g, (15, y), "A", "Edit")
        _pill(g, (120, y), "B", "Back")
        _pill(g, (230, y), "ST", "Save")

        g.draw_paint()

    def _draw_section_header(self, section: str, y: int) -> None:
        g = self.gui
        g.draw_text(
            (30, y),
            section,
            font=11,
            color=g.COLOR_PRIMARY_DARK,
        )

    def _draw_setting_row(self, item: dict, y: int, selected: bool) -> None:
        g = self.gui

        # Row background
        row_top = y
        row_bot = y + 24
        row_mid = y + 12
        bg = g.COLOR_ROW_HOVER if selected else g.COLOR_SECONDARY_DARK
        g.draw_rectangle_r([20, row_top, 620, row_bot], 6, fill=bg)

        if selected:
            g.draw_rectangle_r([20, row_top, 24, row_bot], 2, fill=g.COLOR_ACCENT_BAR)

        # Label
        g.draw_text(
            (30, row_mid),
            item["label"],
            font=15 if selected else 14,
            color=g.COLOR_WHITE if selected else g.COLOR_MUTED,
            anchor="lm",
        )

        # Value
        val = item["value"]
        vtype = item["type"]

        if vtype == "toggle":
            on = bool(val)
            pill_bg = g.COLOR_SUCCESS if on else g.COLOR_SECONDARY_LIGHT
            pill_text = "ON" if on else "OFF"
            pill_clr = g.COLOR_WHITE if on else "#555555"
            g.draw_rectangle_r([555, row_top + 2, 610, row_bot - 2], 8, fill=pill_bg)
            g.draw_text((583, row_mid), pill_text, font=12, color=pill_clr, anchor="mm")

        elif vtype == "number":
            display = str(val) if val is not None else "?"
            g.draw_text(
                (585, row_mid),
                f"< {display} >",
                font=14,
                color=g.COLOR_WHITE if selected else g.COLOR_MUTED,
                anchor="mm",
            )

        elif vtype == "choice":
            display = str(val) if val else "?"
            g.draw_text(
                (585, row_mid),
                f"< {display} >",
                font=14,
                color=g.COLOR_WHITE if selected else g.COLOR_MUTED,
                anchor="mm",
            )

        elif vtype in ("text", "password"):
            display = str(val) if val else ""
            if vtype == "password" and display:
                display = "*" * min(len(display), 12)
            # Truncate
            if len(display) > 16:
                display = display[:15] + "..."
            g.draw_text(
                (610, row_mid),
                display or "--",
                font=14,
                color=g.COLOR_WHITE if selected else g.COLOR_MUTED,
                anchor="rm",
            )


# ---------------------------------------------------------------------------
# Shared pill helper
# ---------------------------------------------------------------------------


class SystemSelectionScreen:
    """Checkbox screen for selecting which systems to batch scrape."""

    MAX_VISIBLE = 11

    def __init__(self, gui, systems: List[str]):
        self.gui = gui
        self.systems = systems
        self.selected = {s: True for s in systems}
        self.pos = 0

    def show(self) -> Optional[List[str]]:
        """Run selection screen. Returns list of selected systems, or None if cancelled."""
        while True:
            self._render()
            inp.check_input()

            if inp.key_pressed("DY"):
                if inp.current_value == 1 and self.pos < len(self.systems) - 1:
                    self.pos += 1
                elif inp.current_value == -1 and self.pos > 0:
                    self.pos -= 1

            elif inp.key_pressed("A"):
                s = self.systems[self.pos]
                self.selected[s] = not self.selected[s]

            elif inp.key_pressed("X"):
                # Toggle all
                all_on = all(self.selected.values())
                for s in self.systems:
                    self.selected[s] = not all_on

            elif inp.key_pressed("START"):
                chosen = [s for s in self.systems if self.selected[s]]
                return chosen if chosen else None

            elif inp.key_pressed("B") or inp.key_pressed("MENUF"):
                return None

    def _render(self) -> None:
        g = self.gui
        scr = g.create_image()
        g.draw_active(scr)

        # Header
        g.draw_rectangle_r([0, 0, 640, 36], 0, fill=g.COLOR_HEADER_BG)
        g.draw_text(
            (20, 18), "SELECT SYSTEMS", font=18, color=g.COLOR_PRIMARY, anchor="lm"
        )
        count = sum(1 for v in self.selected.values() if v)
        g.draw_rectangle_r([230, 8, 310, 28], 10, fill=g.COLOR_SECONDARY_LIGHT)
        g.draw_text(
            (270, 18),
            f"{count}/{len(self.systems)}",
            font=11,
            color=g.COLOR_MUTED,
            anchor="mm",
        )

        # Content area
        g.draw_rectangle_r([10, 42, 630, 438], 10, fill=g.COLOR_SECONDARY_DARK)

        # Draw visible systems
        start_idx = (self.pos // self.MAX_VISIBLE) * self.MAX_VISIBLE
        end_idx = start_idx + self.MAX_VISIBLE

        for i, system in enumerate(self.systems[start_idx:end_idx]):
            idx = start_idx + i
            selected_row = idx == self.pos
            checked = self.selected[system]
            y_pos = 50 + i * 35

            bg = g.COLOR_ROW_HOVER if selected_row else g.COLOR_SECONDARY_DARK
            g.draw_rectangle_r([20, y_pos, 620, y_pos + 32], 6, fill=bg)

            if selected_row:
                g.draw_rectangle_r(
                    [20, y_pos, 24, y_pos + 32], 2, fill=g.COLOR_ACCENT_BAR
                )

            # Checkbox
            cb_color = g.COLOR_SUCCESS if checked else g.COLOR_SECONDARY_LIGHT
            g.draw_rectangle_r(
                [30, y_pos + 6, 50, y_pos + 26], 4, fill=cb_color
            )
            if checked:
                g.draw_text(
                    (40, y_pos + 16), "✓", font=12, color=g.COLOR_WHITE, anchor="mm"
                )

            # System name
            g.draw_text(
                (60, y_pos + 16),
                system,
                font=14 if selected_row else 13,
                color=g.COLOR_WHITE if selected_row else g.COLOR_MUTED,
                anchor="lm",
            )

        # Page indicator
        total_pages = max(
            1, (len(self.systems) + self.MAX_VISIBLE - 1) // self.MAX_VISIBLE
        )
        current_page = (self.pos // self.MAX_VISIBLE) + 1
        g.draw_text(
            (620, 18),
            f"{current_page}/{total_pages}",
            font=11,
            color=g.COLOR_MUTED,
            anchor="rm",
        )

        # Controls
        g.draw_line((10, 443), (630, 443), fill=g.COLOR_SECONDARY_LIGHT, width=1)
        y = 453
        _pill(g, (15, y), "A", "Toggle")
        _pill(g, (130, y), "X", "All")
        _pill(g, (230, y), "ST", "Start")
        _pill(g, (350, y), "B", "Cancel")

        g.draw_paint()


def _pill(gui, pos: Tuple[int, int], button: str, text: str) -> None:
    """Draw a pill-shaped button with label (same style as app.py)."""
    btn_w = max(22, len(button) * 11 + 8)
    gui.draw_rectangle_r(
        (pos[0], pos[1], pos[0] + btn_w, pos[1] + 22),
        11,
        fill=gui.COLOR_PRIMARY_DARK,
    )
    gui.draw_text((pos[0] + btn_w // 2, pos[1] + 11), button, font=12, anchor="mm")
    gui.draw_text(
        (pos[0] + btn_w + 5, pos[1] + 11),
        text,
        font=13,
        color=gui.COLOR_MUTED,
        anchor="lm",
    )
