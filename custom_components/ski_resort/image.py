"""Image platform: resort photo (Wikidata) and trail map (skimap.org)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.util import dt as dt_util

from . import SkiResortConfigEntry
from .const import DATA_INFO
from .coordinator import SkiResortDataUpdateCoordinator
from .entity import SkiResortEntity

_LOGGER = logging.getLogger(__name__)
_IMAGE_TIMEOUT = 20.0

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkiResortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up resort image entities (only when their URL resolved)."""
    coordinator = entry.runtime_data
    info = (coordinator.data or {}).get(DATA_INFO) or {}
    entities: list[ImageEntity] = []
    if info.get("trail_map_url"):
        entities.append(SkiResortImage(coordinator, "trail_map", "trail_map_url"))
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
