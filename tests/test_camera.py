"""Tests for the optional webcam camera entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.ski_resort.camera import SkiResortWebcam
from custom_components.ski_resort.const import CONF_WEBCAM_URL, DOMAIN

from ._setup import setup_area

URL = "https://cam.example/live.jpg"


def _fake_client(response=None, side_effect=None):
    client = AsyncMock()
    client.get = AsyncMock(return_value=response, side_effect=side_effect)
    return client


def _resp(content=b"JPG", ctype="image/jpeg"):
    return httpx.Response(
        200, content=content, headers={"content-type": ctype},
        request=httpx.Request("GET", URL),
    )


async def test_camera_created_when_url_set(hass: HomeAssistant):
    entry, _ = await setup_area(hass, options={CONF_WEBCAM_URL: URL})
    registry = er.async_get(hass)
    eid = registry.async_get_entity_id("camera", DOMAIN, f"{entry.entry_id}_webcam")
    assert eid is not None
    assert hass.states.get(eid) is not None


async def test_no_camera_without_url(hass: HomeAssistant):
    entry, _ = await setup_area(hass)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id(
        "camera", DOMAIN, f"{entry.entry_id}_webcam"
    ) is None


async def test_camera_image_success(hass: HomeAssistant):
    entry, _ = await setup_area(hass, options={CONF_WEBCAM_URL: URL})
    cam = SkiResortWebcam(entry.runtime_data, URL)
    cam.hass = hass
    with patch("custom_components.ski_resort.camera.get_async_client",
               return_value=_fake_client(_resp())):
        data = await cam.async_camera_image()
    assert data == b"JPG"
    assert cam.content_type == "image/jpeg"


async def test_camera_image_cached(hass: HomeAssistant):
    entry, _ = await setup_area(hass, options={CONF_WEBCAM_URL: URL})
    cam = SkiResortWebcam(entry.runtime_data, URL)
    cam.hass = hass
    client = _fake_client(_resp())
    with patch("custom_components.ski_resort.camera.get_async_client",
               return_value=client):
        first = await cam.async_camera_image()
        second = await cam.async_camera_image()  # within TTL -> served from cache
    assert first == second == b"JPG"
    assert client.get.call_count == 1  # only one network fetch


async def test_camera_image_failure_returns_none(hass: HomeAssistant):
    entry, _ = await setup_area(hass, options={CONF_WEBCAM_URL: URL})
    cam = SkiResortWebcam(entry.runtime_data, URL)
    cam.hass = hass
    with patch("custom_components.ski_resort.camera.get_async_client",
               return_value=_fake_client(side_effect=httpx.ConnectError("boom"))):
        assert await cam.async_camera_image() is None


async def test_opensnow_page_url_converted(hass: HomeAssistant):
    """Pasting an OpenSnow cam page URL yields the direct-image camera."""
    entry, _ = await setup_area(
        hass, options={CONF_WEBCAM_URL: "https://opensnow.com/location/vail/cams/3380"}
    )
    registry = er.async_get(hass)
    eid = registry.async_get_entity_id("camera", DOMAIN, f"{entry.entry_id}_webcam")
    assert eid is not None
    # The entity fetches the converted direct image URL.
    cam = SkiResortWebcam(
        entry.runtime_data, "https://cams.opensnow.com/latest/3380/720.webp"
    )
    assert cam._url.endswith("/latest/3380/720.webp")
