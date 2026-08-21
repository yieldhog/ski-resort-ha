"""Binary sensor platform for the Ski Resort integration.

  * Powder day — meaningful fresh snow forecast in the next 24h (Open-Meteo).
  * Resort open — at least one lift open (only when a live lift source is set).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkiResortConfigEntry
from .const import (
    CONF_LIFT_SLUG,
    CONF_LIFTIE_BASE_URL,
    CONF_RAPIDAPI_KEY,
    DATA_LIFTS,
    DATA_WEATHER,
    WX_FRESH_SNOW,
)
from .coordinator import SkiResortDataUpdateCoordinator
from .entity import SkiResortEntity

# A "powder day" threshold: at least this much fresh snow (cm) forecast in 24h.
POWDER_THRESHOLD_CM = 10.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkiResortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for a ski area."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [SkiResortPowderDaySensor(coordinator)]

    opts = entry.options
    if opts.get(CONF_LIFT_SLUG) and (
        opts.get(CONF_LIFTIE_BASE_URL) or opts.get(CONF_RAPIDAPI_KEY)
    ):
        entities.append(SkiResortOpenSensor(coordinator))

    async_add_entities(entities)


class SkiResortPowderDaySensor(SkiResortEntity, BinarySensorEntity):
    """On when a meaningful amount of fresh snow is forecast in the next 24h."""

    _attr_translation_key = "powder_day"
    _attr_icon = "mdi:snowflake"

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_powder_day"

    @property
    def _weather(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DATA_WEATHER)

    @property
    def available(self) -> bool:
        """Available only when Open-Meteo returned data."""
        return super().available and self._weather is not None

    @property
    def is_on(self) -> bool:
        """True when forecast 24h snowfall meets the powder threshold."""
        fresh = (self._weather or {}).get(WX_FRESH_SNOW)
        return isinstance(fresh, (int, float)) and fresh >= POWDER_THRESHOLD_CM

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the forecast fresh-snow amount (cm) and threshold."""
        return {
            "fresh_snow_cm": (self._weather or {}).get(WX_FRESH_SNOW),
            "threshold_cm": POWDER_THRESHOLD_CM,
        }


class SkiResortOpenSensor(SkiResortEntity, BinarySensorEntity):
    """On when at least one lift is open (needs a live lift source)."""

    _attr_translation_key = "resort_open"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:gondola"

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_resort_open"

    @property
    def _lifts(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DATA_LIFTS)

    @property
    def available(self) -> bool:
        """Available only when live lift data was returned."""
        return super().available and self._lifts is not None

    @property
    def is_on(self) -> bool | None:
        """True when more than zero lifts are open."""
        lifts = self._lifts
        if not lifts:
            return None
        return isinstance(lifts.get("open"), int) and lifts["open"] > 0
