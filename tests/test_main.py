from datetime import time

from display import format_minutes, scroll_offset
from main import is_night
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
