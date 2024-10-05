import mmap
import os
from fcntl import ioctl

from PIL import Image, ImageDraw, ImageFont


class GUI:
    COLOR_PRIMARY = "#bb7200"
    COLOR_PRIMARY_DARK = "#7f4f00"
    COLOR_SECONDARY = "#292929"
    COLOR_SECONDARY_LIGHT = "#383838"
    COLOR_SECONDARY_DARK = "#141414"
    COLOR_WHITE = "#ffffff"
    COLOR_BLACK = "#000000"

    def __init__(self):
        self.fb = None
        self.mm = None
        self.screen_width = 640
        self.screen_height = 480
        self.bytes_per_pixel = 4
        self.screen_size = self.screen_width * self.screen_height * self.bytes_per_pixel

        self.fontFile = {
            15: ImageFont.truetype("assets/Roboto-Condensed.ttf", 15),
            13: ImageFont.truetype("assets/Roboto-Condensed.ttf", 13),
            11: ImageFont.truetype("assets/Roboto-Condensed.ttf", 11),
        }

        self.activeImage = None
        self.activeDraw = None

    def screen_reset(self):
        if self.fb:
            ioctl(
                self.fb,
                0x4601,
                b"\x80\x02\x00\x00\xe0\x01\x00\x00\x80\x02\x00\x00\xc0\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00 \x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x08\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x18\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00^\x00\x00\x00\x96\x00\x00\x00\x00\x00\x00\x00\xc2\xa2\x00\x00\x1a\x00\x00\x00T\x00\x00\x00\x0c\x00\x00\x00\x1e\x00\x00\x00\x14\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
            )
            ioctl(self.fb, 0x4611, 0)

    def draw_start(self):
        self.fb = os.open("/dev/fb0", os.O_RDWR)
        self.mm = mmap.mmap(self.fb, self.screen_size)

    def draw_end(self):
        if self.mm and self.fb:
            self.mm.close()
            os.close(self.fb)

    def create_image(self):
        image = Image.new(
            "RGBA", (self.screen_width, self.screen_height), color=self.COLOR_BLACK
        )
        return image

    def draw_image(self, position, image, max_width, max_height):
        if self.activeImage:
            image.thumbnail((max_width, max_height), Image.LANCZOS)
            new_position = (position[0] - image.width, position[1])
            self.activeImage.paste(image, new_position)

    def draw_active(self, image):
        self.activeImage = image
        self.activeDraw = ImageDraw.Draw(self.activeImage)

    def draw_paint(self):
        if self.mm and self.activeImage:
            self.mm.seek(0)
            self.mm.write(self.activeImage.tobytes())

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

    def draw_log(self, text, fill=COLOR_PRIMARY, outline=COLOR_PRIMARY_DARK, width=500):
        # Center the rectangle horizontally
        x = (self.screen_width - width) / 2
        # Center the rectangle vertically
        y = (self.screen_height - 80) / 2  # 80 is the height of the rectangle
        self.draw_rectangle_r([x, y, x + width, y + 80], 5, fill=fill, outline=outline)

        # Center the text within the rectangle
        text_x = x + width / 2
        text_y = y + 40  # Vertically center within the 80px height
        self.draw_text((text_x, text_y), text, anchor="mm")  # Use middle-middle anchor
