"""Direct unit tests for coordinator lift-shaping edges."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.ski_resort.api import SkiResortConnectionError
from custom_components.ski_resort.coordinator import (
    SkiResortDataUpdateCoordinator as C,
)


def _coord(osm_total):
    c = MagicMock(spec=C)
    c.area = {"lifts": osm_total}
    return c


def _info_coord(area):
    c = MagicMock(spec=C)
    c.area = area
    c.hass = MagicMock()
    c._parse_wikidata = C._parse_wikidata  # use the real static parser
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


def test_shape_lifts_clamps_percentage_to_100():
    # Liftie reports more open than OpenSkiMap's total -> cap at 100%.
    shaped = C._shape_lifts(_coord(5), {"open": 8, "closed": 0}, "liftie")
    assert shaped["percentage"] == 100


def test_shape_lifts_non_numeric_counts():
    shaped = C._shape_lifts(_coord(10), {"open": "x", "closed": 1}, "liftie")
    assert shaped["open"] == 0
    assert shaped["total"] == 10  # OpenSkiMap authoritative


def test_parse_wikidata_full():
    item = {"statements": {
        "P856": [{"value": {"content": "https://x.com"}}],
        "P571": [{"value": {"content": {"time": "+1962-00-00T00:00:00Z"}}}],
    }}
    out = C._parse_wikidata(item)
    assert out["website"] == "https://x.com"
    assert out["opening_year"] == 1962
    assert "photo_url" not in out  # photo entity was removed


def test_parse_wikidata_empty():
    assert C._parse_wikidata({}) == {}


async def test_fetch_info_transient_failure_returns_none():
    """A transient network error yields None so the caller retries (not {})."""
    c = _info_coord({"wd": "Q1", "sk": 507})
    with patch(
        "custom_components.ski_resort.coordinator.async_wikidata_item",
        new=AsyncMock(return_value={"statements": {}}),
    ), patch(
        "custom_components.ski_resort.coordinator.async_skimap_trailmap",
        new=AsyncMock(side_effect=SkiResortConnectionError("down")),
    ):
        assert await C._fetch_info(c) is None


async def test_fetch_info_completes_returns_dict():
    """A completed fetch returns the enrichment dict (cacheable)."""
    c = _info_coord({"wd": "Q1", "sk": 507})
    with patch(
        "custom_components.ski_resort.coordinator.async_wikidata_item",
        new=AsyncMock(
            return_value={"statements": {"P856": [{"value": {"content": "https://x"}}]}}
        ),
    ), patch(
        "custom_components.ski_resort.coordinator.async_skimap_trailmap",
        new=AsyncMock(return_value="https://files/trail"),
    ):
        assert await C._fetch_info(c) == {
            "website": "https://x",
            "trail_map_url": "https://files/trail",
        }


async def test_fetch_info_empty_but_complete_is_cacheable():
    """No trail map available (but no error) completes with {} — not a retry."""
    c = _info_coord({"wd": "Q1", "sk": 507})
    with patch(
        "custom_components.ski_resort.coordinator.async_wikidata_item",
        new=AsyncMock(return_value={"statements": {}}),
    ), patch(
        "custom_components.ski_resort.coordinator.async_skimap_trailmap",
        new=AsyncMock(return_value=None),
    ):
        assert await C._fetch_info(c) == {}
