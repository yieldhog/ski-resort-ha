"""The Ski Resort Forecast integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import SkiResortClient
from .const import CONF_API_KEY
from .coordinator import SkiResortDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

type SkiResortConfigEntry = ConfigEntry[SkiResortDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SkiResortConfigEntry) -> bool:
    """Set up Ski Resort Forecast from a config entry."""
    client = SkiResortClient(hass, entry.data[CONF_API_KEY])
    coordinator = SkiResortDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SkiResortConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant, entry: SkiResortConfigEntry
) -> None:
    """Reload the entry when its options change (interval, units, lifts...)."""
    await hass.config_entries.async_reload(entry.entry_id)
