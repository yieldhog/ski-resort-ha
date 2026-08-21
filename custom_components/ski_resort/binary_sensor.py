"""Binary sensor platform for the Ski Resort Forecast integration.

  * Powder day — fresh snowfall greater than zero (always present).
  * Resort open — at least one lift open (only when lift status is enabled).
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
    CONF_ENABLE_LIFTS,
    CONF_LIFT_SLUG,
    DATA_LIFTS,
    DATA_SNOW,
    DEFAULT_ENABLE_LIFTS,
    SNOW_FRESH,
)
from .coordinator import SkiResortDataUpdateCoordinator
from .entity import SkiResortEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkiResortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for a resort config entry."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [SkiResortPowderDaySensor(coordinator)]

    if entry.options.get(
        CONF_ENABLE_LIFTS, DEFAULT_ENABLE_LIFTS
    ) and entry.options.get(CONF_LIFT_SLUG):
        entities.append(SkiResortOpenSensor(coordinator))

    async_add_entities(entities)


class SkiResortPowderDaySensor(SkiResortEntity, BinarySensorEntity):
    """On when fresh snowfall is greater than zero."""

    _attr_translation_key = "powder_day"
    _attr_icon = "mdi:snowflake"

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize the powder-day binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_powder_day"

    @property
    def is_on(self) -> bool:
        """True when the fresh-snow reading is a positive number."""
        snow = (self.coordinator.data or {}).get(DATA_SNOW, {})
        fresh = snow.get(SNOW_FRESH)
        return isinstance(fresh, (int, float)) and fresh > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Surface the fresh-snow amount for use in automations/templates."""
        snow = (self.coordinator.data or {}).get(DATA_SNOW, {})
        return {"fresh_snow": snow.get(SNOW_FRESH)}


class SkiResortOpenSensor(SkiResortEntity, BinarySensorEntity):
    """On when at least one lift is open (needs the conditions product)."""

    _attr_translation_key = "resort_open"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:gondola"

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize the resort-open binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_resort_open"

    @property
    def _lifts(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DATA_LIFTS)

    @property
    def available(self) -> bool:
        """Available only when the lift section returned usable data."""
        return super().available and self._lifts is not None

    @property
    def is_on(self) -> bool | None:
        """True when more than zero lifts report open."""
        lifts = self._lifts
        if not lifts:
            return None
        open_count = lifts.get("open")
        return isinstance(open_count, int) and open_count > 0
