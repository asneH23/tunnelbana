"""All settings for the departure board live here.

Change values in this file to adapt the board, nothing else should need editing.
"""

# --- Station and filtering ---------------------------------------------------

# Find a site id with:  python sl_api.py search "Sandsborg"
STATION_NAME = "Sandsborg"
SITE_ID = 9186

# Only show this kind of traffic (the API also returns BUS, TRAM, TRAIN, ...).
TRANSPORT_MODE = "METRO"

# SL's direction_code for the direction we want to show.
# Checked against the real API at Sandsborg (line 18):
#   1 = northbound, towards Gullmarsplan / T-Centralen (e.g. "Alvik", "Hässelby strand")
#   2 = southbound, towards Farsta strand
DIRECTION_CODE = 1

# --- Timing -----------------------------------------------------------------

FETCH_INTERVAL_SECONDS = 30   # how often we ask the API for new data
REQUEST_TIMEOUT_SECONDS = 10  # give up on a slow API call after this long
FRAMES_PER_SECOND = 20        # how often the screen is redrawn

# --- Layout and look ----------------------------------------------------------

PANEL_WIDTH = 64
PANEL_HEIGHT = 32
NUM_ROWS = 3                  # number of departures shown at once

FONT_SMALL = "fonts/5x7.bdf"  # used for departure rows
FONT_LARGE = "fonts/9x18B.bdf"  # used for the clock
FONT_TINY = "fonts/4x6.bdf"   # used for the "min" after the minutes

# Colors as (red, green, blue), 0-255.
TEXT_COLOR = (255, 150, 0)    # orange-yellow, like SL platform signs
WARNING_COLOR = (200, 0, 0)   # small dot shown when the API can't be reached

SCROLL_SPEED = 12             # pixels per second for long destination names
SCROLL_PAUSE_SECONDS = 2      # pause before a long name starts scrolling

# --- Brightness and night mode ----------------------------------------------

BRIGHTNESS = 60               # 0-100

NIGHT_MODE_ENABLED = True
NIGHT_START = "23:00"         # 24h clock, local time
NIGHT_END = "06:00"
NIGHT_BRIGHTNESS = 0          # 0 = screen off, otherwise dimmed brightness (1-100)

TIMEZONE = "Europe/Stockholm"  # the API returns local Stockholm times

# --- Hardware (only used on the Raspberry Pi) --------------------------------

HARDWARE_MAPPING = "regular"  # panel wired directly to the GPIO pins, no HAT
GPIO_SLOWDOWN = 2             # Pi 3 usually needs 1-2; raise if the image flickers/garbles
PWM_BITS = 11                 # lower (e.g. 7) reduces flicker at the cost of colors
DISABLE_HARDWARE_PULSING = False  # set True only if you can't turn off onboard audio

# The library normally drops root privileges after start. We keep them so the
# program can still read files in the home directory (fonts etc.).
DROP_PRIVILEGES = False
