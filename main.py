"""Main loop: fetch departures every FETCH_INTERVAL_SECONDS and redraw the board.

Run with:  python main.py
"""

import argparse
import logging
import signal
import sys
import time
from datetime import datetime, time as clock_time

import config
from display import Board
from sl_api import STOCKHOLM, fetch_departures

log = logging.getLogger("sl-skylt")


def parse_clock(text):
    """'23:30' -> datetime.time(23, 30)"""
    hours, minutes = text.split(":")
    return clock_time(int(hours), int(minutes))


def in_period(now_time, start_text, end_text):
    """True if now_time is between start and end. Handles periods past midnight."""
    start, end = parse_clock(start_text), parse_clock(end_text)
    if start <= end:
        return start <= now_time < end      # e.g. 01:00-05:00
    return now_time >= start or now_time < end  # e.g. 23:00-06:00


def is_night(now_time, start_text=config.NIGHT_START, end_text=config.NIGHT_END):
    return in_period(now_time, start_text, end_text)


def show_morning_message(now, elapsed):
    """True when the morning message should be on screen instead of the departures.

    In the morning period the message is shown for MESSAGE_SECONDS once
    every MESSAGE_EVERY_SECONDS, so the departures are still visible most of the time.
    """
    if not config.MORNING_MESSAGE:
        return False
    if config.MORNING_MESSAGE_DATE and now.date().isoformat() != config.MORNING_MESSAGE_DATE:
        return False
    if not in_period(now.time(), config.MORNING_MESSAGE_START, config.MORNING_MESSAGE_END):
        return False
    return elapsed % config.MESSAGE_EVERY_SECONDS < config.MESSAGE_SECONDS


def parse_args():
    parser = argparse.ArgumentParser(description="SL departure board")
    parser.add_argument("--mode", type=int, choices=[1, 2], default=config.DISPLAY_MODE,
                        help="1 = big text with ticker, 2 = three still rows in small text")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # systemd stops the service with SIGTERM; turn it into a normal exit so
    # the `finally` block below can switch the panel off.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    board = Board(mode=args.mode)
    departures = []         # last successfully fetched departures
    api_ok = True
    last_fetch = None       # time.monotonic() of the last fetch attempt
    start = time.monotonic()
    frame_time = 1 / config.FRAMES_PER_SECOND

    log.info("Starting board for %s (site %s) in mode %s",
             config.STATION_NAME, config.SITE_ID, args.mode)
    try:
        while True:
            try:
                now = datetime.now(STOCKHOLM)
                night = config.NIGHT_MODE_ENABLED and is_night(now.time())

                if night and config.NIGHT_BRIGHTNESS == 0:
                    board.show_nothing()
                    last_fetch = None  # fetch fresh data as soon as morning comes
                    time.sleep(10)
                    continue

                board.set_brightness(config.NIGHT_BRIGHTNESS if night else config.BRIGHTNESS)

                # Fetch new data when it's time. On failure keep the old data.
                if last_fetch is None or time.monotonic() - last_fetch >= config.FETCH_INTERVAL_SECONDS:
                    last_fetch = time.monotonic()
                    try:
                        departures = fetch_departures()
                        api_ok = True
                    except Exception as error:  # network down, bad JSON, HTTP 500 ...
                        log.warning("Could not fetch departures: %s", error)
                        api_ok = False

                # Drop trains that have already left, then draw.
                elapsed = time.monotonic() - start
                upcoming = [d for d in departures if d.seconds_left(now) > 0]
                if show_morning_message(now, elapsed):
                    board.show_message(config.MORNING_MESSAGE, elapsed, warning=not api_ok)
                elif upcoming:
                    board.show_departures(upcoming, now, elapsed, warning=not api_ok)
                else:
                    board.show_clock(now, warning=not api_ok)

            except Exception:
                # Never crash: log the problem and try again shortly.
                log.exception("Unexpected error in main loop")
                time.sleep(1)

            time.sleep(frame_time)
    except KeyboardInterrupt:
        pass
    finally:
        board.show_nothing()
        log.info("Stopped")


if __name__ == "__main__":
    main()
