"""Tests for pure helpers."""

from __future__ import annotations

from datetime import date

import pytest

from custom_components.ski_resort.helpers import (
    cm_to_display,
    condition_from_wmo,
    m_to_depth_display,
    m_to_elev_display,
    parse_measure,
    parse_snow_date,
    sum_next_hours,
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
