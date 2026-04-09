"""Pygame-based GUI module for Artie Scraper."""

import os
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Tuple

import pygame

from logger import LoggerSingleton as logger

# Screen constants
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480

# Cache limits
MAX_IMAGE_CACHE_ENTRIES = 64
MAX_LOGO_CACHE_ENTRIES = 128


class GUI:
    # Modern dark theme with amber/gold accent
    COLOR_PRIMARY = "#d4881c"
    COLOR_PRIMARY_DARK = "#a06210"
    COLOR_SECONDARY = "#1e1e2e"
    COLOR_SECONDARY_LIGHT = "#2a2a3c"
    COLOR_SECONDARY_DARK = "#14141e"
    COLOR_WHITE = "#e8e8ec"
    COLOR_BLACK = "#0a0a12"
    COLOR_MUTED = "#6c6c80"
    COLOR_SUCCESS = "#4caf50"
    COLOR_ACCENT_BAR = "#d4881c"
    COLOR_ROW_HOVER = "#252538"
    COLOR_HEADER_BG = "#181824"

    def __init__(self):
        # Initialize subsystems (no window yet — that happens in draw_start)
        pygame.display.init()
        pygame.font.init()

        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT

        # Display surface (created in draw_start)
        self._display: Optional[pygame.Surface] = None

        # Hex → RGB conversion cache
        self._color_cache: dict = {}

        try:
            self.fontFile = {
                18: pygame.font.Font("assets/Roboto-BoldCondensed.ttf", 24),
                15: pygame.font.Font("assets/Roboto-Condensed.ttf", 20),
                14: pygame.font.Font("assets/Roboto-BoldCondensed.ttf", 19),
                13: pygame.font.Font("assets/Roboto-Condensed.ttf", 17),
                12: pygame.font.Font("assets/Roboto-BoldCondensed.ttf", 16),
                11: pygame.font.Font("assets/Roboto-Condensed.ttf", 15),
                10: pygame.font.Font("assets/Roboto-Condensed.ttf", 14),
            }
        except (OSError, IOError) as e:
            logger.log_warning(f"Error loading fonts: {e}. Using default font.")
            default = pygame.font.Font(None, 20)
            self.fontFile = {s: default for s in (10, 11, 12, 13, 14, 15, 18)}

        # LRU caches for images and logos
        self._logo_cache: OrderedDict = OrderedDict()
        self._image_cache: OrderedDict = OrderedDict()

        # Pre-allocated frame buffer — reused every frame to avoid allocation
        self._frame_buffer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self._frame_buffer.fill((0, 0, 0))

        self._active_surface: Optional[pygame.Surface] = None
        self._display_size = (SCREEN_WIDTH, SCREEN_HEIGHT)

        # Store last log message for text-only fallback
        self._last_log_message = ""

    def apply_theme(self, theme: dict) -> None:
        """Apply a theme dict to all COLOR_* attributes."""
        self.COLOR_PRIMARY = theme.get("primary", self.COLOR_PRIMARY)
        self.COLOR_PRIMARY_DARK = theme.get("primary_dark", self.COLOR_PRIMARY_DARK)
        self.COLOR_WHITE = theme.get("white", self.COLOR_WHITE)
        self.COLOR_BLACK = theme.get("black", self.COLOR_BLACK)
        self.COLOR_MUTED = theme.get("muted", self.COLOR_MUTED)
        self.COLOR_SUCCESS = theme.get("success", self.COLOR_SUCCESS)
        self.COLOR_ACCENT_BAR = theme.get("accent_bar", self.COLOR_ACCENT_BAR)
        self.COLOR_ROW_HOVER = theme.get("row_hover", self.COLOR_ROW_HOVER)
        self.COLOR_HEADER_BG = theme.get("header_bg", self.COLOR_HEADER_BG)
        self.COLOR_SECONDARY = theme.get("secondary", self.COLOR_SECONDARY)
        self.COLOR_SECONDARY_LIGHT = theme.get("secondary_light", self.COLOR_SECONDARY_LIGHT)
        self.COLOR_SECONDARY_DARK = theme.get("secondary_dark", self.COLOR_SECONDARY_DARK)
        # Clear color cache since hex values changed
        self._color_cache.clear()

    # ------------------------------------------------------------------
    # Color helper
    # ------------------------------------------------------------------

    def _color(self, c) -> Tuple[int, int, int]:
        """Convert a hex colour string to an RGB tuple (cached)."""
        if isinstance(c, (tuple, list)):
            return tuple(c[:3])
        cached = self._color_cache.get(c)
        if cached is not None:
            return cached
        h = c.lstrip("#")
        rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        self._color_cache[c] = rgb
        return rgb

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def screen_reset(self):
        """No-op — pygame handles display configuration."""
        pass

    def draw_start(self, display_width: int = 0, display_height: int = 0):
        """Create the display surface.

        Args:
            display_width: Actual device screen width (0 = use internal size).
            display_height: Actual device screen height (0 = use internal size).
        """
        try:
            logger.log_info("Attempting to initialize pygame display...")
            has_desktop = os.environ.get("DISPLAY") or os.environ.get(
                "WAYLAND_DISPLAY"
            )
            flags = 0 if has_desktop else pygame.NOFRAME

            # Use device resolution if provided, otherwise internal size
            dw = display_width if display_width > 0 else SCREEN_WIDTH
            dh = display_height if display_height > 0 else SCREEN_HEIGHT
            self._display = pygame.display.set_mode((dw, dh), flags)
            self._display_size = (dw, dh)
            pygame.display.set_caption("Artie Scraper")
            pygame.mouse.set_visible(False)
            # Enable key repeat for smooth hold-to-scroll (400ms delay, 80ms interval)
            pygame.key.set_repeat(400, 80)
            logger.log_info(
                f"Pygame display initialized: {dw}x{dh} "
                f"(internal {SCREEN_WIDTH}x{SCREEN_HEIGHT})"
            )
        except (pygame.error, OSError) as e:
            logger.log_warning(f"Display initialization failed: {e}")
            logger.log_info("Falling back to text-only mode")
            self._display = None
            self._display_size = (SCREEN_WIDTH, SCREEN_HEIGHT)

    def draw_end(self):
        """Clean up display resources."""
        if self._display:
            try:
                pygame.display.quit()
            except pygame.error:
                pass
            self._display = None

    # ------------------------------------------------------------------
    # Frame management
    # ------------------------------------------------------------------

    def create_image(self):
        """Return the pre-allocated frame buffer, cleared to black."""
        self._frame_buffer.fill(self._color(self.COLOR_BLACK))
        return self._frame_buffer

    def draw_active(self, image):
        """Set the active surface for subsequent draw calls."""
        self._active_surface = image

    def draw_paint(self):
        """Present the active surface to the display (scaled to fit)."""
        if self._display and self._active_surface:
            dw, dh = self._display_size
            fw, fh = self._active_surface.get_size()
            if (dw, dh) != (fw, fh):
                # Scale internal buffer to fill the display
                scaled = pygame.transform.smoothscale(self._active_surface, (dw, dh))
                self._display.blit(scaled, (0, 0))
            else:
                self._display.blit(self._active_surface, (0, 0))
            pygame.display.flip()
        elif not self._display and self._last_log_message:
            print(f"[ARTIE] {self._last_log_message}")

    def draw_clear(self):
        if self._active_surface:
            self._active_surface.fill(self._color(self.COLOR_BLACK))

    # ------------------------------------------------------------------
    # Drawing primitives
    # ------------------------------------------------------------------

    def draw_text(self, position, text, font=15, color=COLOR_WHITE, **kwargs):
        if not self._active_surface:
            return

        text_str = str(text).strip()
        if not text_str:
            return
        rgb = self._color(color)
        font_obj = self.fontFile.get(font, self.fontFile[15])
        try:
            rendered = font_obj.render(text_str, True, rgb)
        except pygame.error:
            return

        anchor = kwargs.get("anchor", "la")
        x, y = float(position[0]), float(position[1])
        w, h = rendered.get_size()

        # Horizontal: l=left, m=middle, r=right
        ha = anchor[0] if anchor else "l"
        if ha == "m":
            x -= w / 2
        elif ha == "r":
            x -= w

        # Vertical: a=ascender(≈top), t=top, m=middle
        va = anchor[1] if len(anchor) > 1 else "a"
        if va == "m":
            y -= h / 2

        self._active_surface.blit(rendered, (int(x), int(y)))

    def draw_rectangle(self, position, fill=None, outline=None, width=1):
        if not self._active_surface:
            return
        x1, y1, x2, y2 = position
        rect = pygame.Rect(int(x1), int(y1), int(x2 - x1), int(y2 - y1))
        if fill:
            pygame.draw.rect(self._active_surface, self._color(fill), rect)
        if outline:
            pygame.draw.rect(
                self._active_surface, self._color(outline), rect, width
            )

    def draw_rectangle_r(
        self, position, radius, fill=COLOR_SECONDARY_DARK, outline=None
    ):
        if not self._active_surface:
            return
        x1, y1, x2, y2 = position
        w, h = int(x2 - x1), int(y2 - y1)
        if w <= 0 or h <= 0:
            return
        rect = pygame.Rect(int(x1), int(y1), w, h)
        r = max(0, int(radius))
        if fill:
            pygame.draw.rect(
                self._active_surface, self._color(fill), rect, border_radius=r
            )
        if outline:
            pygame.draw.rect(
                self._active_surface,
                self._color(outline),
                rect,
                width=1,
                border_radius=r,
            )

    def draw_circle(
        self, position, radius, fill=COLOR_PRIMARY_DARK, outline=COLOR_WHITE
    ):
        if not self._active_surface:
            return
        # Match PIL semantics: ellipse inscribed in [pos, pos+radius]
        cx = int(position[0] + radius // 2)
        cy = int(position[1] + radius // 2)
        r = max(1, int(radius // 2))
        if fill:
            pygame.draw.circle(
                self._active_surface, self._color(fill), (cx, cy), r
            )
        if outline:
            pygame.draw.circle(
                self._active_surface, self._color(outline), (cx, cy), r, 1
            )

    def draw_line(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        fill=COLOR_MUTED,
        width=1,
    ):
        if not self._active_surface:
            return
        pygame.draw.line(
            self._active_surface, self._color(fill), start, end, width
        )

    def draw_progress_bar(
        self,
        position: Tuple[int, int, int, int],
        progress: float,
        bg_color=COLOR_SECONDARY_LIGHT,
        fill_color=COLOR_PRIMARY,
        radius: int = 4,
    ):
        if not self._active_surface:
            return
        x1, y1, x2, y2 = position
        w, h = int(x2 - x1), int(y2 - y1)
        r = max(0, radius)
        bg_rect = pygame.Rect(int(x1), int(y1), w, h)
        pygame.draw.rect(
            self._active_surface, self._color(bg_color), bg_rect, border_radius=r
        )
        fill_w = int(w * max(0.0, min(1.0, progress)))
        if fill_w > 0:
            fill_rect = pygame.Rect(int(x1), int(y1), fill_w, h)
            pygame.draw.rect(
                self._active_surface,
                self._color(fill_color),
                fill_rect,
                border_radius=r,
            )

    # ------------------------------------------------------------------
    # Image helpers
    # ------------------------------------------------------------------

    def draw_image(self, position, image, max_width, max_height):
        """Draw image with its right edge at position[0]."""
        if self._active_surface and image:
            new_x = position[0] - image.get_width()
            self._active_surface.blit(image, (new_x, position[1]))

    def draw_image_at(self, position, image, max_width, max_height):
        """Paste image at exact position (top-left corner)."""
        if self._active_surface and image:
            self._active_surface.blit(image, position)

    def blit(self, surface, position):
        """Blit a surface directly onto the active surface."""
        if self._active_surface and surface:
            self._active_surface.blit(surface, position)

    def load_image_cached(
        self, image_path: str, max_width: int, max_height: int
    ) -> Optional[pygame.Surface]:
        """Load, resize, and cache an image. Returns cached copy on subsequent calls."""
        cache_key = f"{image_path}_{max_width}_{max_height}"
        if cache_key in self._image_cache:
            self._image_cache.move_to_end(cache_key)
            return self._image_cache[cache_key]

        try:
            path = Path(image_path)
            if not path.exists():
                self._image_cache[cache_key] = None
                return None

            img = pygame.image.load(str(path)).convert_alpha()
            w, h = img.get_size()
            scale = min(max_width / w, max_height / h, 1.0)
            if scale < 1.0:
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                img = pygame.transform.smoothscale(img, (new_w, new_h))
            self._image_cache[cache_key] = img
        except Exception as e:
            logger.log_warning(f"Failed to load image {image_path}: {e}")
            self._image_cache[cache_key] = None

        while len(self._image_cache) > MAX_IMAGE_CACHE_ENTRIES:
            self._image_cache.popitem(last=False)

        return self._image_cache.get(cache_key)

    def clear_image_cache(self) -> None:
        """Clear the image cache (call after scraping changes media files)."""
        self._image_cache.clear()

    def load_logo(
        self, logo_path: str, max_height: int = 24
    ) -> Optional[pygame.Surface]:
        """Load and cache a system logo, scaled to fit max_height."""
        cache_key = f"{logo_path}_{max_height}"
        if cache_key in self._logo_cache:
            self._logo_cache.move_to_end(cache_key)
            return self._logo_cache[cache_key]

        try:
            path = Path(logo_path)
            if not path.exists():
                self._logo_cache[cache_key] = None
                return None

            logo = pygame.image.load(str(path)).convert_alpha()
            w, h = logo.get_size()
            ratio = max_height / h
            new_width = max(1, int(w * ratio))
            logo = pygame.transform.smoothscale(logo, (new_width, max_height))
            self._logo_cache[cache_key] = logo
        except Exception as e:
            logger.log_warning(f"Failed to load logo {logo_path}: {e}")
            self._logo_cache[cache_key] = None

        while len(self._logo_cache) > MAX_LOGO_CACHE_ENTRIES:
            self._logo_cache.popitem(last=False)

        return self._logo_cache.get(cache_key)

    # ------------------------------------------------------------------
    # Overlay helpers
    # ------------------------------------------------------------------

    def draw_log(self, text, fill=None, outline=None, width=520):
        """Draw a centered notification overlay."""
        if fill is None:
            fill = self.COLOR_SECONDARY_LIGHT
        if outline is None:
            outline = self.COLOR_PRIMARY
        self._last_log_message = text

        x = (self.screen_width - width) / 2
        y = (self.screen_height - 70) / 2
        self.draw_rectangle_r(
            [x, y, x + width, y + 70], 8, fill=fill, outline=outline
        )

        # Accent bar at top of notification
        self.draw_rectangle_r(
            [x + 2, y + 2, x + width - 2, y + 6], 2, fill=self.COLOR_PRIMARY
        )

        # Center the text within the rectangle
        text_x = x + width / 2
        text_y = y + 40
        self.draw_text((text_x, text_y), text, anchor="mm")

    def draw_log_with_progress(self, text, progress, width=520):
        """Draw a notification overlay with a progress bar."""
        self._last_log_message = text

        x = (self.screen_width - width) / 2
        y = (self.screen_height - 90) / 2
        self.draw_rectangle_r(
            [x, y, x + width, y + 90],
            8,
            fill=self.COLOR_SECONDARY_LIGHT,
            outline=self.COLOR_PRIMARY,
        )

        # Accent bar at top
        self.draw_rectangle_r(
            [x + 2, y + 2, x + width - 2, y + 6], 2, fill=self.COLOR_PRIMARY
        )

        # Text
        text_x = x + width / 2
        self.draw_text((text_x, y + 30), text, anchor="mm")

        # Progress bar
        bar_margin = 20
        self.draw_progress_bar(
            (
                int(x + bar_margin),
                int(y + 55),
                int(x + width - bar_margin),
                int(y + 70),
            ),
            progress,
        )

        # Percentage text
        pct_text = f"{progress * 100:.0f}%"
        self.draw_text(
            (text_x, y + 80),
            pct_text,
            font=11,
            color=self.COLOR_MUTED,
            anchor="mm",
        )
