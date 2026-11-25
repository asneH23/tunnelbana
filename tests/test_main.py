from datetime import time

from display import format_minutes, scroll_offset, shorten_name
from main import is_night, parse_args, show_morning_message
import config


def test_night_period_past_midnight():
    assert is_night(time(23, 30), "23:00", "06:00")
    assert is_night(time(2, 0), "23:00", "06:00")
    assert not is_night(time(6, 0), "23:00", "06:00")
    assert not is_night(time(12, 0), "23:00", "06:00")


def test_night_period_same_day():
    assert is_night(time(2, 0), "01:00", "05:00")
    assert not is_night(time(0, 30), "01:00", "05:00")


def test_format_minutes():
    assert format_minutes(0) == "Nu"
    assert format_minutes(7) == "7 min"


def test_scroll_pauses_then_moves():
    assert scroll_offset(100, 0) == 0
    assert scroll_offset(100, config.SCROLL_PAUSE_SECONDS - 0.1) == 0
    assert scroll_offset(100, config.SCROLL_PAUSE_SECONDS + 1) == config.SCROLL_SPEED


def test_short_names_are_kept():
    assert shorten_name("Alvik", 10, len) == "Alvik"


def test_known_words_are_abbreviated():
    assert shorten_name("Farsta strand", 11, len) == "Farsta str."
    assert shorten_name("Mörby centrum", 7, len) == "Mörby C"


def test_too_long_names_are_cut_with_a_dot():
    assert shorten_name("Skogskyrkogården", 12, len) == "Skogskyrkog."
    assert shorten_name("Hässelby strand", 11, len) == "Hässelby s."


def test_mode_flag(monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py", "--mode", "2"])
    assert parse_args().mode == 2


def test_mode_defaults_to_config(monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py"])
    assert parse_args().mode == config.DISPLAY_MODE


def test_morning_message_only_in_the_morning_and_now_and_then(monkeypatch):
    monkeypatch.setattr(config, "MORNING_MESSAGE", ["Godmorgon!"])
    monkeypatch.setattr(config, "MORNING_MESSAGE_START", "06:00")
    monkeypatch.setattr(config, "MORNING_MESSAGE_END", "09:00")
    monkeypatch.setattr(config, "MESSAGE_SECONDS", 8)
    monkeypatch.setattr(config, "MESSAGE_EVERY_SECONDS", 30)

    assert show_morning_message(time(7, 0), elapsed=3)       # first 8 s of 30
    assert not show_morning_message(time(7, 0), elapsed=20)  # departures
    assert show_morning_message(time(7, 0), elapsed=62)      # next round
    assert not show_morning_message(time(10, 0), elapsed=3)  # too late


def test_morning_message_can_be_turned_off(monkeypatch):
    monkeypatch.setattr(config, "MORNING_MESSAGE", [])

    assert not show_morning_message(time(7, 0), elapsed=3)
