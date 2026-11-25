"""Draw the departure board on the LED panel (Raspberry Pi) or in the emulator (Mac/PC).

Which backend is used:
  * SL_EMULATOR=1  -> always the emulator
  * SL_EMULATOR=0  -> always the real panel
  * not set        -> the real panel on a Raspberry Pi, the emulator everywhere else
"""

import os
from pathlib import Path

import config

PROJECT_DIR = Path(__file__).parent
SCROLL_GAP = 16  # empty pixels between the end and the restart of a scrolling name
COLUMN_GAP = 3   # empty pixels between the destination and the minutes
UNIT_GAP = 1     # extra empty pixels between the number and "min"


def running_on_raspberry_pi():
    try:
        return "Raspberry Pi" in Path("/proc/device-tree/model").read_text()
    except OSError:
        return False


def use_emulator():
    setting = os.environ.get("SL_EMULATOR")
    if setting is not None:
        return setting == "1"
    return not running_on_raspberry_pi()


# Both libraries have the same API, so the rest of the file doesn't care which one we got.
if use_emulator():
    from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions, graphics
else:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics


def format_minutes(minutes):
    return "Nu" if minutes <= 0 else str(minutes)


def scroll_offset(text_width, elapsed):
    """How many pixels a long text has moved left after `elapsed` seconds.

    Each cycle: stand still for SCROLL_PAUSE_SECONDS, then scroll one full
    text width (plus a gap) so the next copy lands exactly where the first began.
    """
    distance = text_width + SCROLL_GAP
    cycle_time = config.SCROLL_PAUSE_SECONDS + distance / config.SCROLL_SPEED
    time_in_cycle = elapsed % cycle_time
    if time_in_cycle < config.SCROLL_PAUSE_SECONDS:
        return 0
    return int((time_in_cycle - config.SCROLL_PAUSE_SECONDS) * config.SCROLL_SPEED)


def load_font(relative_path):
    font = graphics.Font()
    font.LoadFont(str(PROJECT_DIR / relative_path))
    return font


def make_options():
    options = RGBMatrixOptions()
    options.rows = config.PANEL_HEIGHT
    options.cols = config.PANEL_WIDTH
    options.brightness = config.BRIGHTNESS
    if not use_emulator():
        options.hardware_mapping = config.HARDWARE_MAPPING
        options.gpio_slowdown = config.GPIO_SLOWDOWN
        options.pwm_bits = config.PWM_BITS
        options.disable_hardware_pulsing = config.DISABLE_HARDWARE_PULSING
        options.drop_privileges = config.DROP_PRIVILEGES
    return options


class Board:
    def __init__(self):
        # Load fonts before creating the matrix (it may drop root privileges).
        self.small_font = load_font(config.FONT_SMALL)
        self.large_font = load_font(config.FONT_LARGE)
        self.tiny_font = load_font(config.FONT_TINY)
        self.text_color = graphics.Color(*config.TEXT_COLOR)
        self.warning_color = graphics.Color(*config.WARNING_COLOR)
        self.black = graphics.Color(0, 0, 0)

        self.matrix = RGBMatrix(options=make_options())
        # We draw on an offscreen canvas and swap it in, which avoids flicker.
        self.canvas = self.matrix.CreateFrameCanvas()

        self.width = config.PANEL_WIDTH
        self.row_height = config.PANEL_HEIGHT // config.NUM_ROWS

        # Fixed columns: [line number] [destination ...] [minutes]
        self.line_column = self.text_width(self.small_font, "88") + 2
        # The minutes column fits the widest text, e.g. "12min" (with "min" in the tiny font).
        self.unit_width = self.text_width(self.tiny_font, "min")
        widest_minutes = self.text_width(self.small_font, "88") + UNIT_GAP + self.unit_width
        self.minutes_column = self.width - widest_minutes

    # --- public methods, called from main.py -------------------------------

    def set_brightness(self, brightness):
        if self.matrix.brightness != brightness:
            self.matrix.brightness = brightness

    def show_departures(self, departures, now, elapsed, warning=False):
        """Draw up to NUM_ROWS departures. `elapsed` (seconds) drives the scrolling."""
        self.canvas.Clear()
        for row, departure in enumerate(departures[: config.NUM_ROWS]):
            self.draw_row(row, departure, now, elapsed)
        if warning:
            self.draw_warning()
        self.swap()

    def show_clock(self, now, warning=False):
        """Shown when there are no departures: a big clock and a small note."""
        self.canvas.Clear()
        time_text = now.strftime("%H:%M")
        x = (self.width - self.text_width(self.large_font, time_text)) // 2
        graphics.DrawText(self.canvas, self.large_font, x, self.large_font.baseline,
                          self.text_color, time_text)

        note = "Inga tåg"
        x = (self.width - self.text_width(self.small_font, note)) // 2
        graphics.DrawText(self.canvas, self.small_font, x, 29, self.text_color, note)
        if warning:
            self.draw_warning()
        self.swap()

    def show_nothing(self):
        self.canvas.Clear()
        self.swap()

    # --- drawing helpers ---------------------------------------------------

    def swap(self):
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

    @staticmethod
    def text_width(font, text):
        return sum(max(0, font.CharacterWidth(ord(char))) for char in text)

    def draw_row(self, row, departure, now, elapsed):
        font = self.small_font
        top = row * self.row_height
        baseline = top + (self.row_height - font.height) // 2 + font.baseline

        # 1. Destination first. If it is too long it scrolls, and may spill
        #    into the other columns; step 2 cleans that up.
        dest_x = self.line_column
        space = self.minutes_column - COLUMN_GAP - dest_x
        name_width = self.text_width(font, departure.destination)
        if name_width <= space:
            graphics.DrawText(self.canvas, font, dest_x, baseline, self.text_color,
                              departure.destination)
        else:
            x = dest_x - scroll_offset(name_width, elapsed)
            # Draw the text twice so a new copy follows right behind the first.
            for copy_x in (x, x + name_width + SCROLL_GAP):
                graphics.DrawText(self.canvas, font, copy_x, baseline, self.text_color,
                                  departure.destination)

        # 2. Black out the line and minutes columns so scrolled text can't show there.
        self.clear_columns(0, dest_x, top)
        self.clear_columns(self.minutes_column - COLUMN_GAP, self.width, top)

        # 3. Line number on the left, minutes right-aligned.
        graphics.DrawText(self.canvas, font, 0, baseline, self.text_color, departure.line)
        self.draw_minutes(departure.minutes_left(now), baseline)

    def draw_minutes(self, minutes, baseline):
        """Draw e.g. "7min" (with a smaller "min") or "Nu", right-aligned."""
        text = format_minutes(minutes)
        if text == "Nu":
            x = self.width - self.text_width(self.small_font, text)
            graphics.DrawText(self.canvas, self.small_font, x, baseline, self.text_color, text)
            return

        unit_x = self.width - self.unit_width
        number_x = unit_x - UNIT_GAP - self.text_width(self.small_font, text)
        graphics.DrawText(self.canvas, self.small_font, number_x, baseline, self.text_color, text)
        graphics.DrawText(self.canvas, self.tiny_font, unit_x, baseline, self.text_color, "min")

    def clear_columns(self, x_start, x_end, top):
        bottom = top + self.row_height - 1
        for x in range(x_start, x_end):
            graphics.DrawLine(self.canvas, x, top, x, bottom, self.black)

    def draw_warning(self):
        # A tiny red mark in the bottom-right corner. Column 63 is the empty
        # spacing column of right-aligned text, so it never covers a digit.
        x = self.width - 1
        y = config.PANEL_HEIGHT - 1
        graphics.DrawLine(self.canvas, x, y - 1, x, y, self.warning_color)
