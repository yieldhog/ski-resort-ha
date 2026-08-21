"""Camera platform: an optional resort webcam from a still-image URL.

Fully optional and self-contained. When the user supplies a direct webcam
still-image URL in the options, this exposes it as a ``camera`` entity on the
resort device. Fetches follow redirects and swallow errors (a broken URL never
raises); a short cache keeps polling gentle on the resort's server, and the
last good frame is served if a refresh fails.
"""

from __future__ import annotations

import logging

import httpx
from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client

from . import SkiResortConfigEntry
from .const import CONF_WEBCAM_URL
from .coordinator import SkiResortDataUpdateCoordinator
from .entity import SkiResortEntity

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = 20.0
_CACHE_TTL = 30.0  # seconds; webcams update slowly, so don't refetch every poll

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkiResortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the resort webcam camera when a URL is configured."""
    url = (entry.options.get(CONF_WEBCAM_URL) or "").strip()
    if url:
        async_add_entities([SkiResortWebcam(entry.runtime_data, url)])


class SkiResortWebcam(SkiResortEntity, Camera):
    """A still-image webcam camera for the resort."""

    _attr_translation_key = "webcam"

    def __init__(
        self, coordinator: SkiResortDataUpdateCoordinator, url: str
    ) -> None:
        """Initialize the webcam from the configured still-image URL."""
        SkiResortEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._url = url
        self._attr_unique_id = f"{coordinator.entry.entry_id}_webcam"
        self._cache: bytes | None = None
        self._cache_at: float = 0.0

    @property
    def available(self) -> bool:
        """A webcam is independent of the polled data, so always available."""
        return True

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the latest webcam frame (cached briefly), or None."""
        now = self.hass.loop.time()
        if self._cache is not None and (now - self._cache_at) < _CACHE_TTL:
            return self._cache
        try:
            resp = await get_async_client(self.hass).get(
                self._url, timeout=_TIMEOUT, follow_redirects=True
            )
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.InvalidURL) as err:
            _LOGGER.debug("Webcam fetch failed for %s: %s", self._url, err)
            return self._cache  # serve the last good frame if we have one
        content_type = resp.headers.get("content-type")
        if content_type:
            self._attr_content_type = content_type
        self._cache = resp.content
        self._cache_at = now
        return self._cache
