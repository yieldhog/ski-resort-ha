"""The Ski Resort integration (OpenSkiMap-anchored)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_AREA
from .coordinator import SkiResortDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.WEATHER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.IMAGE,
    Platform.CAMERA,
]

type SkiResortConfigEntry = ConfigEntry[SkiResortDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SkiResortConfigEntry) -> bool:
    """Set up a ski area from a config entry."""
    if CONF_AREA not in entry.data:
        # Entry predates the OpenSkiMap re-anchor; its data can't be migrated.
        raise ConfigEntryError(
            "This ski resort was added by an older version and must be removed "
            "and added again."
        )
    coordinator = SkiResortDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SkiResortConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _reload(hass: HomeAssistant, entry: SkiResortConfigEntry) -> None:
    """Reload when options change (units, providers, interval)."""
    await hass.config_entries.async_reload(entry.entry_id)
