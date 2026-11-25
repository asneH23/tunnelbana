"""Tests for parsing and filtering. They use saved JSON, never the real API."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from sl_api import STOCKHOLM, Departure, parse_departures

FIXTURE = Path(__file__).parent / "fixtures" / "sandsborg_departures.json"


@pytest.fixture
def api_data():
    # A real response from /v1/sites/9186/departures (Sandsborg).
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_item(**overrides):
    """A minimal departure entry shaped like the real API response."""
    item = {
        "destination": "Alvik",
        "direction_code": 1,
        "state": "EXPECTED",
        "scheduled": "2026-11-25T12:47:06",
        "expected": "2026-11-25T12:47:09",
        "line": {"designation": "18", "transport_mode": "METRO"},
    }
    item.update(overrides)
    return item


def test_keeps_only_northbound_metro(api_data):
    departures = parse_departures(api_data, "METRO", 1)

    assert len(departures) == 3
    assert all(d.destination == "Alvik" for d in departures)
    assert all(d.line == "18" for d in departures)


def test_southbound_is_farsta(api_data):
    departures = parse_departures(api_data, "METRO", 2)

    assert {d.destination for d in departures} == {"Farsta strand"}


def test_sorted_by_time_and_timezone_aware(api_data):
    departures = parse_departures(api_data, "METRO", 1)

    times = [d.expected for d in departures]
    assert times == sorted(times)
    assert times[0] == datetime(2026, 11, 25, 12, 47, 9, tzinfo=STOCKHOLM)


def test_other_transport_modes_are_ignored():
    data = {"departures": [make_item(line={"designation": "144", "transport_mode": "BUS"})]}

    assert parse_departures(data, "METRO", 1) == []


def test_cancelled_departures_are_ignored():
    data = {"departures": [make_item(state="CANCELLED")]}

    assert parse_departures(data, "METRO", 1) == []


def test_falls_back_to_scheduled_time():
    data = {"departures": [make_item(expected=None)]}

    [dep] = parse_departures(data, "METRO", 1)
    assert dep.expected.second == 6  # from "scheduled"


def test_malformed_entries_are_skipped():
    data = {"departures": [{"destination": "Broken"}, make_item(expected="not a time"), make_item()]}

    assert len(parse_departures(data, "METRO", 1)) == 1


def test_empty_or_missing_departures():
    assert parse_departures({}, "METRO", 1) == []
    assert parse_departures({"departures": []}, "METRO", 1) == []


def test_minutes_left():
    dep = Departure("18", "Alvik", datetime(2026, 11, 25, 12, 10, 0, tzinfo=STOCKHOLM))

    assert dep.minutes_left(datetime(2026, 11, 25, 12, 0, 0, tzinfo=STOCKHOLM)) == 10
    assert dep.minutes_left(datetime(2026, 11, 25, 12, 0, 30, tzinfo=STOCKHOLM)) == 9
    assert dep.minutes_left(datetime(2026, 11, 25, 12, 9, 59, tzinfo=STOCKHOLM)) == 0
    assert dep.minutes_left(datetime(2026, 11, 25, 12, 11, 0, tzinfo=STOCKHOLM)) == 0
