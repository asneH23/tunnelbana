"""Fetch and filter departures from SL's Transport API.

This module knows nothing about the LED panel, so it can be tested and used on
its own. Run it directly to try it out:

    python sl_api.py                  # print upcoming departures
    python sl_api.py search Sandsborg # find the site id of a station
"""

import sys
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

import config

BASE_URL = "https://transport.integration.sl.se/v1"
STOCKHOLM = ZoneInfo(config.TIMEZONE)

# Departure states that mean the train will not (or no longer) leave from here.
SKIPPED_STATES = {"CANCELLED", "DEPARTED", "ASSUMEDDEPARTED"}


@dataclass(frozen=True)
class Departure:
    line: str           # e.g. "18"
    destination: str    # e.g. "Alvik"
    expected: datetime  # when the train leaves, timezone-aware

    def seconds_left(self, now):
        return (self.expected - now).total_seconds()

    def minutes_left(self, now):
        """Whole minutes until departure, never negative."""
        return max(0, int(self.seconds_left(now) // 60))


def parse_time(text):
    """The API gives local Stockholm time without a timezone, e.g. '2026-11-25T12:47:09'."""
    return datetime.fromisoformat(text).replace(tzinfo=STOCKHOLM)


def parse_departures(data, transport_mode, direction_code):
    """Turn the raw API JSON into a sorted list of Departure objects.

    Only departures with the given transport mode and direction are kept.
    Entries with missing fields are skipped instead of crashing.
    """
    departures = []
    for item in data.get("departures", []):
        try:
            line = item["line"]
            if line.get("transport_mode") != transport_mode:
                continue
            if item.get("direction_code") != direction_code:
                continue
            if item.get("state") in SKIPPED_STATES:
                continue

            # "expected" is the real-time prediction; fall back to the timetable.
            time_text = item.get("expected") or item["scheduled"]
            departures.append(
                Departure(
                    line=str(line["designation"]),
                    destination=item["destination"],
                    expected=parse_time(time_text),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue  # skip a malformed entry, keep the rest

    departures.sort(key=lambda d: d.expected)
    return departures


def fetch_departures(site_id=config.SITE_ID):
    """Download departures for a site. Raises requests.RequestException on failure."""
    url = f"{BASE_URL}/sites/{site_id}/departures"
    response = requests.get(url, timeout=config.REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return parse_departures(response.json(), config.TRANSPORT_MODE, config.DIRECTION_CODE)


def search_sites(name):
    """Return all sites whose name contains `name` (case-insensitive)."""
    response = requests.get(f"{BASE_URL}/sites", timeout=config.REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return [site for site in response.json() if name.lower() in site.get("name", "").lower()]


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "search":
        for site in search_sites(sys.argv[2]):
            print(f"{site['id']:>8}  {site['name']}  {site.get('note', '')}")
        return

    now = datetime.now(STOCKHOLM)
    print(f"Departures from {config.STATION_NAME} (site {config.SITE_ID}), "
          f"{config.TRANSPORT_MODE}, direction {config.DIRECTION_CODE}:")
    for dep in fetch_departures():
        print(f"  {dep.line:>3}  {dep.destination:<20} {dep.minutes_left(now):>3} min")


if __name__ == "__main__":
    main()
