"""Show made-up departures with long names, to see how they look on the board.

On the Pi, stop the real board first (both use the panel):
    sudo systemctl stop sl-skylt
    sudo .venv/bin/python demo.py            # uses DISPLAY_MODE from config.py
    sudo .venv/bin/python demo.py --mode 1   # or choose a mode
    sudo systemctl start sl-skylt            # back to the real board

Stop the demo with Ctrl+C.
"""

import argparse
import time
from datetime import datetime, timedelta

import config
from display import Board
from sl_api import STOCKHOLM, Departure

# (line, destination, minutes until departure). Edit freely.
DEMO_DEPARTURES = [
    ("18", "Hässelby strand", 0),
    ("18", "Skogskyrkogården", 4),
    ("18", "Västra skogen", 9),
    ("18", "Åkeshov", 14),
    ("18", "Alvik", 19),
]


def main():
    parser = argparse.ArgumentParser(description="Demo with made-up departures")
    parser.add_argument("--mode", type=int, choices=[1, 2], default=config.DISPLAY_MODE)
    args = parser.parse_args()

    board = Board(mode=args.mode)
    started = datetime.now(STOCKHOLM)
    # 30 extra seconds so the first one shows "Nu" and the others e.g. "4 min".
    departures = [
        Departure(line, name, started + timedelta(minutes=minutes, seconds=30))
        for line, name, minutes in DEMO_DEPARTURES
    ]
    start = time.monotonic()

    print(f"Showing demo in mode {args.mode}. Stop with Ctrl+C.")
    try:
        while True:
            now = datetime.now(STOCKHOLM)
            upcoming = [d for d in departures if d.seconds_left(now) > 0]
            if upcoming:
                board.show_departures(upcoming, now, time.monotonic() - start)
            else:
                board.show_clock(now)
            time.sleep(1 / config.FRAMES_PER_SECOND)
    except KeyboardInterrupt:
        pass
    finally:
        board.show_nothing()


if __name__ == "__main__":
    main()
