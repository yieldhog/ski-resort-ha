"""Direct unit tests for coordinator shaping edge cases."""

from __future__ import annotations

from custom_components.ski_resort.coordinator import (
    SkiResortDataUpdateCoordinator as C,
)


def test_shape_lifts_rejects_missing_data():
    """A payload without a data dict yields None (sensors go unavailable)."""
    assert C._shape_lifts({"nope": 1}) is None


def test_shape_lifts_rejects_missing_lifts():
    """A data block without lifts yields None."""
    assert C._shape_lifts({"data": {"name": "X"}}) is None


def test_shape_lifts_rejects_missing_stats():
    """A lifts block without stats yields None."""
    assert C._shape_lifts({"data": {"lifts": {"status": {}}}}) is None


def test_shape_lifts_handles_non_numeric_counts():
    """Non-numeric stat values fall back to zero rather than raising."""
    shaped = C._shape_lifts(
        {"data": {"lifts": {"stats": {"open": "x", "closed": 3}}}}
    )
    assert shaped["open"] == 0
    assert shaped["closed"] == 3
    assert shaped["total"] == 3
