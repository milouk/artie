"""Settings screen and virtual keyboard for Artie Scraper."""

import json
from typing import Any, List, Optional, Tuple

import input as inp
from logger import LoggerSingleton as logger


# ---------------------------------------------------------------------------
# Nested dict helpers
# ---------------------------------------------------------------------------


def _get_nested(data: dict, path: str) -> Any:
    """Get a value from a nested dict using a dotted path."""
    for key in path.split("."):
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return None
    return data


def _set_nested(data: dict, path: str, value: Any) -> None:
    """Set a value in a nested dict using a dotted path."""
    keys = path.split(".")
    for key in keys[:-1]:
        data = data.setdefault(key, {})
    data[keys[-1]] = value


# ---------------------------------------------------------------------------
# Settings definitions
# ---------------------------------------------------------------------------

# Each tuple: (section, json_path, label, widget_type, extra_kwargs)
SETTINGS_DEFS: List[Tuple[str, str, str, str, dict]] = [
    ("Account", "screenscraper.username", "Username", "text", {}),
    ("Account", "screenscraper.password", "Password", "password", {}),
    ("Scraping", "screenscraper.threads", "Threads", "number", {"min": 1, "max": 20}),
    (
        "Scraping",
        "screenscraper.show_scraped_roms",
        "Show All ROMs",
        "toggle",
        {},
    ),
    ("Media", "screenscraper.content.box.enabled", "Box Art", "toggle", {}),
    ("Media", "screenscraper.content.preview.enabled", "Preview", "toggle", {}),
    (
        "Media",
        "screenscraper.content.synopsis.enabled",
        "Synopsis",
        "toggle",
        {},
    ),
    ("Display", "show_logos", "Show Logos", "toggle", {}),
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
            display = "\u2022" * len(display)
        # Truncate from left so cursor stays visible
        font_obj = g.fontFile[18]
        max_w = 570
        while font_obj.size(display + "\u2502")[0] > max_w and display:
            display = display[1:]
        g.draw_text(
            (30, 70), display + "\u2502", font=18, color=g.COLOR_WHITE, anchor="lm"
        )

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
                    "SPACE": "\u2423",
                    "BKSP": "\u2190",
                    "SHIFT": "\u21e7",
                }.get(key, key)

                fsz = 14 if len(label) <= 2 else 11
                clr = g.COLOR_WHITE if selected else g.COLOR_MUTED
                g.draw_text(
                    (x + w // 2, y + h // 2), label, font=fsz, color=clr, anchor="mm"
                )

        # Controls
        g.draw_line(
            (10, 443), (630, 443), fill=g.COLOR_SECONDARY_LIGHT, width=1
        )
        y = 453
        _pill(g, (15, y), "A", "Type")
        _pill(g, (110, y), "B", "Bksp")
        _pill(g, (220, y), "X", "Mode")
        _pill(g, (330, y), "Y", "Cancel")
        _pill(g, (450, y), "ST", "Confirm")

        g.draw_paint()


# ---------------------------------------------------------------------------
# Settings Screen
# ---------------------------------------------------------------------------


class SettingsScreen:
    """Full-screen settings editor."""

    MAX_VISIBLE = 11

    def __init__(self, gui, config_path: str, raw_config: dict):
        self.gui = gui
        self.config_path = config_path
        self.raw_config = raw_config

        # Build flat list of editable settings with current values
        self.items: List[dict] = []
        prev_section = None
        for section, path, label, wtype, extra in SETTINGS_DEFS:
            self.items.append(
                {
                    "section": section,
                    "show_section": section != prev_section,
                    "path": path,
                    "label": label,
                    "type": wtype,
                    "value": _get_nested(raw_config, path),
                    **extra,
                }
            )
            prev_section = section

        self.pos = 0
        self.dirty = False

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
                    self.dirty = True
                elif item["type"] == "number" and inp.key_pressed("DX"):
                    self._adjust_number(item, inp.current_value)
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
        self.dirty = True

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
            self.dirty = True

    # -- persistence --

    def _save(self) -> None:
        """Write changed settings back to config.json."""
        try:
            # Re-read the file to avoid clobbering concurrent changes
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in self.items:
                _set_nested(data, item["path"], item["value"])

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")

            logger.log_info("Settings saved to config.json")
            self.dirty = False

        except Exception as e:
            logger.log_error(f"Failed to save settings: {e}")

    # -- rendering --

    def _render(self) -> None:
        g = self.gui
        scr = g.create_image()
        g.draw_active(scr)

        # Header
        g.draw_rectangle_r([0, 0, 640, 36], 0, fill=g.COLOR_HEADER_BG)
        g.draw_text(
            (20, 18), "SETTINGS", font=18, color=g.COLOR_PRIMARY, anchor="lm"
        )
        if self.dirty:
            g.draw_rectangle_r([130, 8, 210, 28], 10, fill=g.COLOR_PRIMARY_DARK)
            g.draw_text(
                (170, 18), "modified", font=10, color=g.COLOR_WHITE, anchor="mm"
            )

        # Content area
        g.draw_rectangle_r(
            [10, 42, 630, 438], 10, fill=g.COLOR_SECONDARY_DARK
        )

        # Draw visible items
        page_start = (self.pos // self.MAX_VISIBLE) * self.MAX_VISIBLE
        page_end = page_start + self.MAX_VISIBLE

        for i, item in enumerate(self.items[page_start:page_end]):
            idx = page_start + i
            selected = idx == self.pos
            self._draw_setting_row(item, i, selected)

        # Page indicator
        total_pages = max(1, (len(self.items) + self.MAX_VISIBLE - 1) // self.MAX_VISIBLE)
        current_page = (self.pos // self.MAX_VISIBLE) + 1
        g.draw_text(
            (620, 18),
            f"{current_page}/{total_pages}",
            font=11,
            color=g.COLOR_MUTED,
            anchor="rm",
        )

        # Controls
        g.draw_line(
            (10, 443), (630, 443), fill=g.COLOR_SECONDARY_LIGHT, width=1
        )
        y = 453
        _pill(g, (15, y), "A", "Edit")
        _pill(g, (95, y), "\u25c4\u25ba", "Adjust")
        _pill(g, (220, y), "B", "Back")
        _pill(g, (320, y), "ST", "Save")
        _pill(g, (440, y), "M", "Exit")

        g.draw_paint()

    def _draw_setting_row(self, item: dict, vis_index: int, selected: bool) -> None:
        g = self.gui
        y = 50 + vis_index * 35

        # Section header (drawn above first item in section)
        if item["show_section"]:
            g.draw_text(
                (30, y + 2),
                item["section"],
                font=10,
                color=g.COLOR_PRIMARY_DARK,
            )

        # Row background
        bg = g.COLOR_ROW_HOVER if selected else g.COLOR_SECONDARY_DARK
        g.draw_rectangle_r([20, y + 12, 620, y + 32], 6, fill=bg)

        if selected:
            g.draw_rectangle_r(
                [20, y + 12, 24, y + 32], 2, fill=g.COLOR_ACCENT_BAR
            )

        # Label
        g.draw_text(
            (30, y + 22),
            item["label"],
            font=14 if selected else 13,
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
            g.draw_rectangle_r([560, y + 14, 610, y + 30], 8, fill=pill_bg)
            g.draw_text(
                (585, y + 22), pill_text, font=11, color=pill_clr, anchor="mm"
            )

        elif vtype == "number":
            display = str(val) if val is not None else "?"
            g.draw_text(
                (585, y + 22),
                f"\u25c4 {display} \u25ba",
                font=13,
                color=g.COLOR_WHITE if selected else g.COLOR_MUTED,
                anchor="mm",
            )

        elif vtype in ("text", "password"):
            display = str(val) if val else ""
            if vtype == "password" and display:
                display = "\u2022" * min(len(display), 12)
            # Truncate
            if len(display) > 18:
                display = display[:17] + "\u2026"
            g.draw_text(
                (610, y + 22),
                display or "\u2014",
                font=13,
                color=g.COLOR_WHITE if selected else g.COLOR_MUTED,
                anchor="rm",
            )


# ---------------------------------------------------------------------------
# Shared pill helper
# ---------------------------------------------------------------------------


def _pill(gui, pos: Tuple[int, int], button: str, text: str) -> None:
    """Draw a pill-shaped button with label (same style as app.py)."""
    btn_w = max(22, len(button) * 11 + 8)
    gui.draw_rectangle_r(
        (pos[0], pos[1], pos[0] + btn_w, pos[1] + 22),
        11,
        fill=gui.COLOR_PRIMARY_DARK,
    )
    gui.draw_text(
        (pos[0] + btn_w // 2, pos[1] + 11), button, font=12, anchor="mm"
    )
    gui.draw_text(
        (pos[0] + btn_w + 5, pos[1] + 11),
        text,
        font=13,
        color=gui.COLOR_MUTED,
        anchor="lm",
    )
