"""Direct unit tests for coordinator lift-shaping edges."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.ski_resort.coordinator import (
    SkiResortDataUpdateCoordinator as C,
)


def _coord(osm_total):
    c = MagicMock(spec=C)
    c.area = {"lifts": osm_total}
    return c


def test_shape_lifts_empty_returns_none():
    assert C._shape_lifts(_coord(32), {}, "liftie") is None


def test_shape_lifts_falls_back_to_reported_total():
    # OpenSkiMap total 0 -> use reported sum; percentage from that.
    shaped = C._shape_lifts(
        _coord(0), {"open": 2, "hold": 0, "scheduled": 0, "closed": 2}, "skiapi"
    )
    assert shaped["total"] == 4
    assert shaped["percentage"] == 50


def test_shape_lifts_non_numeric_counts():
    shaped = C._shape_lifts(_coord(10), {"open": "x", "closed": 1}, "liftie")
    assert shaped["open"] == 0
    assert shaped["total"] == 10  # OpenSkiMap authoritative
