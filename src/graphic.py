import mmap
import os
from fcntl import ioctl
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from logger import LoggerSingleton as logger


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
        self.fb: Optional[int] = None
        self.mm: Optional[mmap.mmap] = None
        self.screen_width = 640
        self.screen_height = 480
        self.bytes_per_pixel = 4
        self.screen_size = self.screen_width * self.screen_height * self.bytes_per_pixel

        # Framebuffer error suppression (keep UI working, suppress error messages only)
        self.suppress_framebuffer_errors = False
        self.framebuffer_write_failures = 0
        self.max_write_failures = (
            3  # Start suppressing errors after 3 consecutive failures
        )

        try:
            self.fontFile = {
                18: ImageFont.truetype("assets/Roboto-BoldCondensed.ttf", 18),
                15: ImageFont.truetype("assets/Roboto-Condensed.ttf", 15),
                14: ImageFont.truetype("assets/Roboto-BoldCondensed.ttf", 14),
                13: ImageFont.truetype("assets/Roboto-Condensed.ttf", 13),
                12: ImageFont.truetype("assets/Roboto-BoldCondensed.ttf", 12),
                11: ImageFont.truetype("assets/Roboto-Condensed.ttf", 11),
                10: ImageFont.truetype("assets/Roboto-Condensed.ttf", 10),
            }
        except (OSError, IOError) as e:
            logger.log_warning(f"Error loading fonts: {e}. Using default font.")
            default = ImageFont.load_default()
            self.fontFile = {
                18: default,
                15: default,
                14: default,
                13: default,
                12: default,
                11: default,
                10: default,
            }

        # Logo cache to avoid reloading on every frame
        self._logo_cache = {}

        # General image cache for media thumbnails (ROM detail view etc.)
        self._image_cache = {}

        # Pre-allocated frame buffer — reused every frame to avoid allocation
        self._frame_buffer = Image.new(
            "RGBA",
            (self.screen_width, self.screen_height),
            color=self.COLOR_BLACK,
        )

        # Pre-allocated BGRA conversion buffer for framebuffer output
        self._bgra_buffer = Image.new(
            "RGBA",
            (self.screen_width, self.screen_height),
        )

        self.activeImage = None
        self.activeDraw = None

    def screen_reset(self):
        """Reset screen configuration with error handling."""
        if self.fb:
            try:
                ioctl(
                    self.fb,
                    0x4601,
                    b"\x80\x02\x00\x00\xe0\x01\x00\x00\x80\x02\x00\x00\xc0\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00 \x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x08\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x18\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00^\x00\x00\x00\x96\x00\x00\x00\x00\x00\x00\x00\xc2\xa2\x00\x00\x1a\x00\x00\x00T\x00\x00\x00\x0c\x00\x00\x00\x1e\x00\x00\x00\x14\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",  # noqa: E501
                )
                ioctl(self.fb, 0x4611, 0)
            except (OSError, IOError) as e:
                logger.log_warning(f"Error resetting screen: {e}")

    def draw_start(self):
        """Initialize framebuffer with proper error handling."""
        try:
            logger.log_info("Attempting to initialize framebuffer...")
            self.fb = os.open("/dev/fb0", os.O_RDWR)
            self.mm = mmap.mmap(self.fb, self.screen_size)
            logger.log_info("Framebuffer device opened successfully - UI enabled")

        except (OSError, IOError) as e:
            logger.log_warning(f"Framebuffer initialization failed: {e}")
            logger.log_info("Falling back to text-only mode")
            self._cleanup_framebuffer_resources()

    def _cleanup_framebuffer_resources(self):
        """Clean up framebuffer resources."""
        if self.mm:
            try:
                self.mm.close()
            except (OSError, IOError):
                pass
            self.mm = None
        if self.fb is not None:
            try:
                os.close(self.fb)
            except (OSError, IOError):
                pass
            self.fb = None

    def draw_end(self):
        """Clean up framebuffer resources."""
        self._cleanup_framebuffer_resources()

    def create_image(self):
        """Return the pre-allocated frame buffer, cleared to black."""
        # Reuse the existing buffer instead of allocating ~1.2MB per frame
        self._frame_buffer.paste(
            self.COLOR_BLACK, (0, 0, self.screen_width, self.screen_height)
        )
        return self._frame_buffer

    def draw_image(self, position, image, max_width, max_height):
        if self.activeImage:
            image.thumbnail((max_width, max_height), Image.LANCZOS)
            new_position = (position[0] - image.width, position[1])
            self.activeImage.paste(image, new_position)

    def draw_image_at(self, position, image, max_width, max_height):
        """Paste image at exact position (top-left corner)."""
        if self.activeImage:
            image.thumbnail((max_width, max_height), Image.LANCZOS)
            if image.mode == "RGBA":
                self.activeImage.paste(image, position, image)
            else:
                self.activeImage.paste(image, position)

    def load_image_cached(
        self, image_path: str, max_width: int, max_height: int
    ) -> Optional[Image.Image]:
        """Load, resize, and cache an image. Returns cached copy on subsequent calls."""
        cache_key = f"{image_path}_{max_width}_{max_height}"
        if cache_key in self._image_cache:
            return self._image_cache[cache_key]

        try:
            path = Path(image_path)
            if not path.exists():
                self._image_cache[cache_key] = None
                return None

            img = Image.open(path).convert("RGBA")
            img.thumbnail((max_width, max_height), Image.LANCZOS)
            self._image_cache[cache_key] = img
            return img
        except Exception as e:
            logger.log_warning(f"Failed to load image {image_path}: {e}")
            self._image_cache[cache_key] = None
            return None

    def clear_image_cache(self) -> None:
        """Clear the image cache (call after scraping changes media files)."""
        self._image_cache.clear()

    def load_logo(self, logo_path: str, max_height: int = 24) -> Optional[Image.Image]:
        """Load and cache a system logo, scaled to fit max_height."""
        cache_key = f"{logo_path}_{max_height}"
        if cache_key in self._logo_cache:
            return self._logo_cache[cache_key]

        try:
            path = Path(logo_path)
            if not path.exists():
                self._logo_cache[cache_key] = None
                return None

            logo = Image.open(path).convert("RGBA")
            # Scale proportionally to fit max_height
            ratio = max_height / logo.height
            new_width = int(logo.width * ratio)
            logo = logo.resize((new_width, max_height), Image.LANCZOS)
            self._logo_cache[cache_key] = logo
            return logo
        except Exception as e:
            logger.log_warning(f"Failed to load logo {logo_path}: {e}")
            self._logo_cache[cache_key] = None
            return None

    def draw_active(self, image):
        self.activeImage = image
        self.activeDraw = ImageDraw.Draw(self.activeImage)

    def draw_paint(self):
        """Paint the active image to framebuffer with error suppression (keep UI working)."""
        if self.mm and self.activeImage:
            try:
                self.mm.seek(0)
                # Framebuffer expects BGRA; PIL produces RGBA — swap R and B
                r, g, b, a = self.activeImage.split()
                self._bgra_buffer = Image.merge("RGBA", (b, g, r, a))
                self.mm.write(self._bgra_buffer.tobytes())
                self.mm.flush()

                # Reset failure counter on successful write
                if self.framebuffer_write_failures > 0:
                    self.framebuffer_write_failures = 0
                    if not self.suppress_framebuffer_errors:
                        logger.log_info(
                            "Framebuffer write recovered - continuing normal operation"
                        )

            except (OSError, IOError) as e:
                self.framebuffer_write_failures += 1

                if self.framebuffer_write_failures <= self.max_write_failures:
                    logger.log_warning(
                        f"Framebuffer write failed "
                        f"(attempt {self.framebuffer_write_failures}/{self.max_write_failures}): {e}"
                    )

                if self.framebuffer_write_failures >= self.max_write_failures:
                    if not self.suppress_framebuffer_errors:
                        logger.log_info(
                            "Suppressing further framebuffer error messages - UI remains functional"
                        )
                        self.suppress_framebuffer_errors = True

        elif not self.mm:
            if hasattr(self, "_last_log_message"):
                print(f"[ARTIE] {self._last_log_message}")

    def draw_clear(self):
        if self.activeDraw:
            self.activeDraw.rectangle(
                (0, 0, self.screen_width, self.screen_height), fill=self.COLOR_BLACK
            )

    def draw_text(self, position, text, font=15, color=COLOR_WHITE, **kwargs):
        if self.activeDraw:
            self.activeDraw.text(
                position, text, font=self.fontFile[font], fill=color, **kwargs
            )

    def draw_rectangle(self, position, fill=None, outline=None, width=1):
        if self.activeDraw:
            self.activeDraw.rectangle(position, fill=fill, outline=outline, width=width)

    def draw_rectangle_r(
        self, position, radius, fill=COLOR_SECONDARY_DARK, outline=None
    ):
        if self.activeDraw:
            self.activeDraw.rounded_rectangle(
                position, radius, fill=fill, outline=outline
            )

    def draw_circle(
        self, position, radius, fill=COLOR_PRIMARY_DARK, outline=COLOR_WHITE
    ):
        if self.activeDraw:
            self.activeDraw.ellipse(
                [
                    position[0],
                    position[1],
                    position[0] + radius,
                    position[1] + radius,
                ],
                fill=fill,
                outline=outline,
            )

    def draw_line(
        self, start: Tuple[int, int], end: Tuple[int, int], fill=COLOR_MUTED, width=1
    ):
        """Draw a line between two points."""
        if self.activeDraw:
            self.activeDraw.line([start, end], fill=fill, width=width)

    def draw_progress_bar(
        self,
        position: Tuple[int, int, int, int],
        progress: float,
        bg_color=COLOR_SECONDARY_LIGHT,
        fill_color=COLOR_PRIMARY,
        radius: int = 4,
    ):
        """Draw a progress bar. progress is 0.0 to 1.0."""
        if not self.activeDraw:
            return
        x1, y1, x2, y2 = position
        # Background
        self.activeDraw.rounded_rectangle([x1, y1, x2, y2], radius, fill=bg_color)
        # Fill
        fill_width = int((x2 - x1) * max(0.0, min(1.0, progress)))
        if fill_width > 0:
            self.activeDraw.rounded_rectangle(
                [x1, y1, x1 + fill_width, y2], radius, fill=fill_color
            )

    def draw_log(self, text, fill=None, outline=None, width=520):
        """Draw a centered notification overlay."""
        if fill is None:
            fill = self.COLOR_SECONDARY_LIGHT
        if outline is None:
            outline = self.COLOR_PRIMARY
        # Store message for potential text-only fallback
        self._last_log_message = text

        # Center the rectangle horizontally
        x = (self.screen_width - width) / 2
        # Center the rectangle vertically
        y = (self.screen_height - 70) / 2
        self.draw_rectangle_r([x, y, x + width, y + 70], 8, fill=fill, outline=outline)

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
            (text_x, y + 80), pct_text, font=11, color=self.COLOR_MUTED, anchor="mm"
        )
