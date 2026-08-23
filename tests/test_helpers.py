"""Tests for pure helpers."""

from __future__ import annotations

from datetime import date

import pytest

from custom_components.ski_resort.helpers import (
    cm_to_display,
    condition_from_wmo,
    local_now_marker,
    m_to_depth_display,
    m_to_elev_display,
    parse_measure,
    parse_snow_date,
    point_in_geometry,
    sum_next_hours,
    value_at_hour,
)


@pytest.mark.parametrize(
    ("code", "expected"),
    [(0, "sunny"), (2, "partlycloudy"), (73, "snowy"), (95, "lightning"),
     (65, "pouring"), (999, None), (None, None), (True, None)],
)
def test_condition_from_wmo(code, expected):
    assert condition_from_wmo(code) == expected


def test_cm_to_display():
    assert cm_to_display(25.4, imperial=True) == 10.0
    assert cm_to_display(10.0, imperial=False) == 10.0
    assert cm_to_display(None, imperial=True) is None


def test_depth_and_elev_display():
    assert m_to_depth_display(1.0, imperial=False) == 100.0
    assert m_to_depth_display(2.54, imperial=True) == 100.0  # 254cm/2.54
    assert m_to_elev_display(3048, imperial=True) == 10000
    assert m_to_elev_display(1000, imperial=False) == 1000
    assert m_to_elev_display(None, imperial=True) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [("83in", 83.0), ("210 cm", 210.0), (12, 12.0), (None, None),
     ("n/a", None), (True, None)],
)
def test_parse_measure(value, expected):
    assert parse_measure(value) == expected


def test_parse_snow_date():
    assert parse_snow_date("25 Jan 2026") == date(2026, 1, 25)
    assert parse_snow_date("") is None
    assert parse_snow_date("junk") is None


def test_sum_next_hours():
    assert sum_next_hours(list(range(24)), [1.0] * 24, 24) == 24.0
    assert sum_next_hours([], [], 24) is None
    assert sum_next_hours([1], [None, None], 24) is None
    assert sum_next_hours([1, 2, 3], [1.0, 2.0, 3.0], 2) == 3.0


def test_sum_next_hours_starts_at_current_hour():
    # Open-Meteo hourly arrays begin at 00:00; snow only falls in hours 0..5.
    times = [f"2026-01-25T{h:02d}:00" for h in range(24)]
    values = [1.0] * 6 + [0.0] * 18
    # At midnight the next 24h captures all of it...
    assert sum_next_hours(times, values, 24, now="2026-01-25T00:00") == 6.0
    # ...but by 06:00 the morning snow is in the past, so "next 24h" sees none.
    assert sum_next_hours(times, values, 24, now="2026-01-25T06:00") == 0.0
    # Unknown "now" (missing offset) falls back to the start of the array.
    assert sum_next_hours(times, values, 24) == 6.0


def test_value_at_hour():
    times = [f"2026-01-25T{h:02d}:00" for h in range(24)]
    depths = [float(h) for h in range(24)]
    assert value_at_hour(times, depths, now="2026-01-25T09:00") == 9.0
    assert value_at_hour(times, depths) == 0.0  # fallback: start of array
    assert value_at_hour([], [], now="2026-01-25T09:00") is None
    assert value_at_hour(times, [None] * 24, now="2026-01-25T09:00") is None


def test_point_in_geometry():
    poly = {"type": "Polygon", "coordinates": [
        [[-107, 39], [-106, 39], [-106, 40], [-107, 40], [-107, 39]]
    ]}
    assert point_in_geometry(-106.35, 39.6, poly) is True   # Vail
    assert point_in_geometry(-108.0, 39.6, poly) is False   # west of the box
    multi = {"type": "MultiPolygon", "coordinates": [
        [[[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]]
    ]}
    assert point_in_geometry(0, 0, multi) is True
    assert point_in_geometry(5, 5, multi) is False
    # Non-polygon / junk geometry never matches.
    assert point_in_geometry(0, 0, {"type": "Point", "coordinates": [0, 0]}) is False
    assert point_in_geometry(0, 0, None) is False


def test_local_now_marker():
    from datetime import UTC, datetime

    now = datetime(2026, 1, 25, 22, 30, tzinfo=UTC)
    # UTC-7 (Denver, MST) -> 15:00 local, truncated to the top of the hour.
    assert local_now_marker(now, -7 * 3600) == "2026-01-25T15:00"
    assert local_now_marker(now, None) is None
    assert local_now_marker(now, True) is None  # bool is not a usable offset


def test_resolve_webcam_url():
    from custom_components.ski_resort.helpers import resolve_webcam_url

    assert resolve_webcam_url("https://opensnow.com/location/vail/cams/3380") == \
        "https://cams.opensnow.com/latest/3380/720.webp"
    # direct URLs pass through unchanged
    assert resolve_webcam_url("https://cam.example/x.jpg") == "https://cam.example/x.jpg"
    assert resolve_webcam_url("") == ""
