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
COLUMN_GAP = 2   # empty pixels between line number, destination and minutes
LETTER_SPACING = 1  # every glyph in our fonts ends with one empty column
TICKER_GAP = 16  # empty pixels between two departures in the ticker


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
    return "Nu" if minutes <= 0 else f"{minutes} min"


def shorten_name(name, max_width, width_of):
    """Shorten a destination so it fits in max_width pixels, like SL's signs.

    1. Abbreviate known words:  "Farsta strand" -> "Farsta str."
    2. If it is still too long, cut letters off the end and add a dot:
       "Skogskyrkogården" -> "Skogskyrkog."
    `width_of` is a function that returns the pixel width of a text.
    """
    if width_of(name) <= max_width:
        return name

    words = [config.ABBREVIATIONS.get(word, word) for word in name.split(" ")]
    name = " ".join(words)
    while width_of(name) > max_width and len(name) > 2:
        name = name.rstrip(".")[:-1].rstrip() + "."
    return name


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
    def __init__(self, mode=1):
        self.mode = mode  # 1 = big text + ticker, 2 = small text, still rows

        # Load fonts before creating the matrix (it may drop root privileges).
        self.fonts = {1: load_font(config.FONT_MODE1), 2: load_font(config.FONT_MODE2)}
        self.font = self.fonts[mode]  # the font for the departures in this mode
        self.large_font = load_font(config.FONT_CLOCK)
        self.text_color = graphics.Color(*config.TEXT_COLOR)
        self.warning_color = graphics.Color(*config.WARNING_COLOR)
        self.black = graphics.Color(0, 0, 0)

        self.matrix = RGBMatrix(options=make_options())
        # We draw on an offscreen canvas and swap it in, which avoids flicker.
        self.canvas = self.matrix.CreateFrameCanvas()

        self.width = config.PANEL_WIDTH
        self.num_rows = 2 if mode == 1 else config.MODE2_ROWS
        self.row_height = config.PANEL_HEIGHT // self.num_rows

        # The ticker keeps the departures it is showing for a whole pass across
        # the screen, so nothing jumps when new data arrives mid-way.
        self.ticker_departures = []
        self.ticker_start = 0.0


    # --- public methods, called from main.py -------------------------------

    def set_brightness(self, brightness):
        if self.matrix.brightness != brightness:
            self.matrix.brightness = brightness

    def show_departures(self, departures, now, elapsed, warning=False):
        """Draw the departures. `elapsed` (seconds) drives all the animation."""
        self.canvas.Clear()
        if self.mode == 1:
            # Mode 1: the next train on top, the following ones in a ticker.
            self.draw_row(0, departures[0], now, elapsed)
            following = departures[1 : 1 + config.TICKER_DEPARTURES]
            self.draw_ticker(1, following, now, elapsed)
        else:
            # Mode 2: one still row per departure.
            for row, departure in enumerate(departures[: self.num_rows]):
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
        x = (self.width - self.ink_width(self.font, note)) // 2
        graphics.DrawText(self.canvas, self.font, x, 28, self.text_color, note)
        if warning:
            self.draw_warning()
        self.swap()

    def show_message(self, lines, elapsed, warning=False):
        """Show a few lines of text, centered. A line that is too wide scrolls."""
        self.canvas.Clear()
        lines = lines[:3]
        # Big letters if two lines fit, otherwise the small font.
        font = self.fonts[1] if len(lines) <= 2 else self.fonts[2]
        row_height = config.PANEL_HEIGHT // len(lines)
        padding = max(0, (row_height - font.height) // 2)

        for row, text in enumerate(lines):
            baseline = row * row_height + padding + font.baseline
            width = self.ink_width(font, text)
            if width <= self.width:
                x = (self.width - width) // 2
                graphics.DrawText(self.canvas, font, x, baseline, self.text_color, text)
            else:
                x = -scroll_offset(width, elapsed)
                for copy_x in (x, x + width + SCROLL_GAP):
                    graphics.DrawText(self.canvas, font, copy_x, baseline, self.text_color, text)
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
        """Width in pixels including the empty column after the last letter."""
        return sum(max(0, font.CharacterWidth(ord(char))) for char in text)

    def ink_width(self, font, text):
        """Width of the lit pixels only (without the trailing empty column)."""
        return max(0, self.text_width(font, text) - LETTER_SPACING)

    def draw_row(self, row, departure, now, elapsed):
        """One row, like SL's signs:  18 Alvik       4 min"""
        font = self.font
        top = row * self.row_height
        baseline = self.baseline(row)

        # Work out the three columns: [line] [destination ...] [minutes]
        line = departure.line if config.SHOW_LINE_NUMBER else ""
        minutes = format_minutes(departure.minutes_left(now))
        minutes_x = self.width - self.ink_width(font, minutes)  # right-aligned
        dest_x = self.ink_width(font, line) + COLUMN_GAP if line else 0
        dest_end = minutes_x - COLUMN_GAP  # first column the name must not use

        # 1. Destination first. Too long names are shortened ("Farsta str."),
        #    or scroll if shortening is turned off. Scrolled text may spill
        #    into the other columns; step 2 cleans that up.
        name = departure.destination
        if config.SHORTEN_LONG_NAMES or self.mode == 2:
            space = dest_end - dest_x
            name = shorten_name(name, space, lambda text: self.ink_width(font, text))

        name_width = self.ink_width(font, name)
        if dest_x + name_width <= dest_end:
            graphics.DrawText(self.canvas, font, dest_x, baseline, self.text_color, name)
        else:
            x = dest_x - scroll_offset(name_width, elapsed)
            # Draw the text twice so a new copy follows right behind the first.
            for copy_x in (x, x + name_width + SCROLL_GAP):
                graphics.DrawText(self.canvas, font, copy_x, baseline, self.text_color, name)

        # 2. Black out the line and minutes columns so scrolled text can't show there.
        self.clear_columns(0, dest_x, top)
        self.clear_columns(dest_end, self.width, top)

        # 3. Line number on the left, minutes on the right.
        graphics.DrawText(self.canvas, font, 0, baseline, self.text_color, line)
        graphics.DrawText(self.canvas, font, minutes_x, baseline, self.text_color, minutes)

    def baseline(self, row):
        """The y position to draw text at so it sits centered in the row."""
        top = row * self.row_height
        # If the font is taller than the row (accent rows included), start at the top.
        padding = max(0, (self.row_height - self.font.height) // 2)
        return top + padding + self.font.baseline

    def draw_ticker(self, row, departures, now, elapsed):
        """Scroll departures through a row from right to left, one after another.

        Each pass starts with the text just off the right edge and ends when
        all of it has left on the left side. Then a new pass begins with the
        latest departures.
        """
        distance = (elapsed - self.ticker_start) * config.TICKER_SPEED
        pass_length = self.width + self.ticker_width(self.ticker_departures)
        if not self.ticker_departures or distance > pass_length:
            self.ticker_departures = departures
            self.ticker_start = elapsed
            distance = 0

        x = self.width - int(distance)
        for departure in self.ticker_departures:
            item_width = self.ticker_item_width(departure)
            if x < self.width and x + item_width > 0:  # skip items that are off screen
                self.draw_ticker_item(departure, x, self.baseline(row), now)
            x += item_width + TICKER_GAP

    def ticker_item_width(self, departure):
        # The minutes get a fixed-width box ("88 min"), so the text doesn't
        # jump when e.g. "10 min" becomes "9 min" while scrolling.
        label = f"{departure.line} {departure.destination}"
        return self.ink_width(self.font, label) + COLUMN_GAP + self.ink_width(self.font, "88 min")

    def ticker_width(self, departures):
        return sum(self.ticker_item_width(d) + TICKER_GAP for d in departures)

    def draw_ticker_item(self, departure, x, baseline, now):
        """One ticker item, e.g. "18 Alvik 14 min", starting at x."""
        label = f"{departure.line} {departure.destination}"
        graphics.DrawText(self.canvas, self.font, x, baseline, self.text_color, label)

        minutes = format_minutes(departure.minutes_left(now))
        box_end = x + self.ticker_item_width(departure)  # right edge of the minutes box
        minutes_x = box_end - self.ink_width(self.font, minutes)
        graphics.DrawText(self.canvas, self.font, minutes_x, baseline, self.text_color, minutes)

    def clear_columns(self, x_start, x_end, top):
        bottom = top + self.row_height - 1
        for x in range(x_start, x_end):
            graphics.DrawLine(self.canvas, x, top, x, bottom, self.black)

    def draw_warning(self):
        # A tiny red mark in the bottom-right corner, below the last row's text.
        x = self.width - 1
        y = config.PANEL_HEIGHT - 1
        graphics.DrawLine(self.canvas, x, y - 1, x, y, self.warning_color)
