"""Tests for the pure helper functions."""

from __future__ import annotations

from datetime import date

import pytest

from custom_components.ski_resort.helpers import (
    parse_measure,
    parse_snow_date,
    slugify_resort,
    trend_of,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("83in", 83.0),
        ("210 cm", 210.0),
        ("-1.5cm", -1.5),
        ("0in", 0.0),
        (12, 12.0),
        (3.5, 3.5),
        (None, None),
        ("", None),
        ("n/a", None),
        (True, None),
        ({"x": 1}, None),
    ],
)
def test_parse_measure(value, expected):
    """Unit-suffixed strings, numbers, and junk all map correctly."""
    assert parse_measure(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("25 Jan 2026", date(2026, 1, 25)),
        ("  01 Feb 2025 ", date(2025, 2, 1)),
        ("not a date", None),
        ("", None),
        (None, None),
        (12345, None),
    ],
)
def test_parse_snow_date(value, expected):
    """Human date strings parse; anything else is None."""
    assert parse_snow_date(value) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Vail", "vail"),
        ("Beaver Creek", "beaver-creek"),
        ("  Val d'Isere  ", "val-d-isere"),
        ("A/B  C", "a-b-c"),
    ],
)
def test_slugify_resort(name, expected):
    """Names become lowercase hyphenated slugs."""
    assert slugify_resort(name) == expected


@pytest.mark.parametrize(
    ("current", "previous", "expected"),
    [
        (10.0, 8.0, "up"),
        (8.0, 10.0, "down"),
        (5.0, 5.0, "stable"),
        (None, 5.0, None),
        (5.0, None, None),
    ],
)
def test_trend_of(current, previous, expected):
    """Trend classification, with None when either side is missing."""
    assert trend_of(current, previous) == expected
