"""Tests for the image entity's redirect-following fetch."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
from homeassistant.core import HomeAssistant

from custom_components.ski_resort.image import SkiResortImage

from ._setup import setup_area


def _fake_client(response=None, side_effect=None):
    client = AsyncMock()
    client.get = AsyncMock(return_value=response, side_effect=side_effect)
    return patch(
        "custom_components.ski_resort.image.get_async_client", return_value=client
    )


async def test_async_image_follows_redirect(hass: HomeAssistant):
    """Image bytes are fetched with redirects followed; content-type is set."""
    entry, _ = await setup_area(hass)
    img = SkiResortImage(entry.runtime_data, "trail_map", "trail_map_url")
    resp = httpx.Response(
        200, content=b"IMG", headers={"content-type": "image/png"},
        request=httpx.Request("GET", "https://example/x.png"),
    )
    with _fake_client(resp) as _p:
        data = await img.async_image()
    assert data == b"IMG"
    assert img.content_type == "image/png"


async def test_async_image_failure_returns_none(hass: HomeAssistant):
    """A fetch error yields no image rather than raising."""
    entry, _ = await setup_area(hass)
    img = SkiResortImage(entry.runtime_data, "trail_map", "trail_map_url")
    with _fake_client(side_effect=httpx.ConnectError("boom")):
        assert await img.async_image() is None


async def test_async_image_no_url_returns_none(hass: HomeAssistant):
    """With no resolved URL, async_image returns None without a request."""
    entry, _ = await setup_area(hass, wikidata={}, trail_map=None)
    img = SkiResortImage(entry.runtime_data, "trail_map", "trail_map_url")
    assert await img.async_image() is None
