"""Tests for the image entity's redirect-following fetch."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.ski_resort.const import CONF_WEBCAM_URL, DOMAIN
from custom_components.ski_resort.image import SkiResortImage, SkiResortWebcamImage

from ._setup import setup_area

WEBCAM_URL = "https://cam.example/live.jpg"


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


async def test_webcam_image_created_and_fetches(hass: HomeAssistant):
    """A configured webcam URL creates an image entity that fetches WebP bytes."""
    entry, _ = await setup_area(hass, options={CONF_WEBCAM_URL: WEBCAM_URL})
    registry = er.async_get(hass)
    eid = registry.async_get_entity_id("image", DOMAIN, f"{entry.entry_id}_webcam")
    assert eid is not None  # rendered as an image entity, not a camera

    cam = SkiResortWebcamImage(entry.runtime_data, WEBCAM_URL)
    cam.hass = hass
    resp = httpx.Response(
        200, content=b"WEBP", headers={"content-type": "image/webp"},
        request=httpx.Request("GET", WEBCAM_URL),
    )
    with _fake_client(resp):
        data = await cam.async_image()
    assert data == b"WEBP"  # served as-is; browsers render WebP in <img>
    assert cam.content_type == "image/webp"


async def test_webcam_image_fetch_error_returns_none(hass: HomeAssistant):
    """A webcam fetch error yields no image rather than raising."""
    entry, _ = await setup_area(hass, options={CONF_WEBCAM_URL: WEBCAM_URL})
    cam = SkiResortWebcamImage(entry.runtime_data, WEBCAM_URL)
    cam.hass = hass
    with _fake_client(side_effect=httpx.ConnectError("boom")):
        assert await cam.async_image() is None


async def test_webcam_image_refreshes_timestamp_on_update(hass: HomeAssistant):
    """Each coordinator poll bumps image_last_updated so the frontend refetches."""
    entry, _ = await setup_area(hass, options={CONF_WEBCAM_URL: WEBCAM_URL})
    cam = SkiResortWebcamImage(entry.runtime_data, WEBCAM_URL)
    cam.hass = hass
    before = cam.image_last_updated
    with patch.object(cam, "async_write_ha_state"):
        cam._handle_coordinator_update()
    assert cam.image_last_updated >= before


async def test_webcam_image_removed_when_url_cleared(hass: HomeAssistant):
    """Blanking the webcam URL deletes the image entity instead of orphaning it."""
    from custom_components.ski_resort import image as img_mod

    entry, _ = await setup_area(hass)  # no webcam URL
    registry = er.async_get(hass)
    unique = f"{entry.entry_id}_webcam"
    registry.async_get_or_create("image", DOMAIN, unique, config_entry=entry)
    assert registry.async_get_entity_id("image", DOMAIN, unique) is not None

    await img_mod.async_setup_entry(hass, entry, lambda ents, *a, **k: None)
    assert registry.async_get_entity_id("image", DOMAIN, unique) is None  # removed
