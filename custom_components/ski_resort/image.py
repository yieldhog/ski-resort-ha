"""Image platform: trail map (skimap.org) and the optional resort webcam.

The webcam is modeled as an *image* entity rather than a camera on purpose:
Home Assistant renders an image entity as a plain ``<img>`` (which displays
WebP/PNG/JPEG natively), whereas a still camera's live view is an MJPEG stream
that only reliably renders JPEG frames in a browser. Using an image entity
sidesteps that entirely — no transcoding, no MJPEG.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.util import dt as dt_util

from . import SkiResortConfigEntry
from .const import CONF_WEBCAM_URL, DATA_INFO, DOMAIN
from .coordinator import SkiResortDataUpdateCoordinator
from .entity import SkiResortEntity
from .helpers import resolve_webcam_url

_LOGGER = logging.getLogger(__name__)
_IMAGE_TIMEOUT = 20.0

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkiResortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up resort image entities (trail map + optional webcam)."""
    coordinator = entry.runtime_data
    entities: list[ImageEntity] = []
    # Gate on the static skimap id (always known at setup), not on the first
    # enrichment fetch: a transient failure there must not permanently suppress
    # the entity. Its ``available`` tracks whether the URL has resolved yet.
    if coordinator.area.get("sk") is not None:
        entities.append(SkiResortImage(coordinator, "trail_map", "trail_map_url"))

    webcam_url = resolve_webcam_url((entry.options.get(CONF_WEBCAM_URL) or "").strip())
    if webcam_url:
        entities.append(SkiResortWebcamImage(coordinator, webcam_url))
    else:
        # Clearing the URL: remove any webcam entity left from a prior config.
        registry = er.async_get(hass)
        existing = registry.async_get_entity_id(
            "image", DOMAIN, f"{entry.entry_id}_webcam"
        )
        if existing:
            registry.async_remove(existing)

    async_add_entities(entities)


class SkiResortImage(SkiResortEntity, ImageEntity):
    """A static resort image sourced from an enrichment URL."""

    _attr_content_type = "image/jpeg"

    def __init__(
        self,
        coordinator: SkiResortDataUpdateCoordinator,
        key: str,
        info_key: str,
    ) -> None:
        """Initialize the image entity from the coordinator's info URL."""
        SkiResortEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._info_key = info_key
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        # The URL is static once resolved, so a fixed timestamp is correct and
        # keeps the frontend from re-fetching on every poll.
        self._attr_image_last_updated = dt_util.utcnow()

    @property
    def _info(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(DATA_INFO) or {}

    @property
    def image_url(self) -> str | None:
        """The enrichment image URL."""
        return self._info.get(self._info_key)

    @property
    def available(self) -> bool:
        """Available only when the image URL is present."""
        return super().available and bool(self.image_url)

    async def async_image(self) -> bytes | None:
        """Fetch the image bytes, following redirects.

        Overridden because the Wikidata/Commons photo URL is a 302 redirect to
        the actual file — HA's default fetch does not follow redirects. Any
        network/URL error is swallowed so a missing image never breaks the
        entity; it just returns no picture.
        """
        url = self.image_url
        if not url:
            return None
        try:
            resp = await get_async_client(self.hass).get(
                url, timeout=_IMAGE_TIMEOUT, follow_redirects=True
            )
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.InvalidURL) as err:
            _LOGGER.debug("Image fetch failed for %s: %s", url, err)
            return None
        content_type = resp.headers.get("content-type")
        if content_type:
            self._attr_content_type = content_type
        return resp.content


class SkiResortWebcamImage(SkiResortEntity, ImageEntity):
    """The optional resort webcam, served as a still image.

    Independent of the polled data (a webcam works even if a data source is
    down). The frontend is told the image changed on every coordinator poll so
    it re-fetches a fresh frame; fetches follow redirects and swallow errors so
    a broken or hotlink-blocked URL never breaks the entity.
    """

    _attr_translation_key = "webcam"

    def __init__(
        self, coordinator: SkiResortDataUpdateCoordinator, url: str
    ) -> None:
        """Initialize the webcam image from the resolved still-image URL."""
        SkiResortEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._url = url
        self._attr_unique_id = f"{coordinator.entry.entry_id}_webcam"
        self._attr_image_last_updated = dt_util.utcnow()

    @property
    def available(self) -> bool:
        """A webcam is independent of the polled data, so always available."""
        return True

    def _handle_coordinator_update(self) -> None:
        """Bump the timestamp each poll so the frontend re-fetches a frame."""
        self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Fetch the latest webcam frame (following redirects), or ``None``."""
        try:
            resp = await get_async_client(self.hass).get(
                self._url, timeout=_IMAGE_TIMEOUT, follow_redirects=True
            )
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.InvalidURL) as err:
            _LOGGER.debug("Webcam fetch failed for %s: %s", self._url, err)
            return None
        content_type = resp.headers.get("content-type")
        if content_type:
            self._attr_content_type = content_type
        return resp.content
