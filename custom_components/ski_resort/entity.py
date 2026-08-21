"""Base entity for the Ski Resort Forecast integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, CONF_RESORT, DATA_INFO, DOMAIN, MANUFACTURER
from .coordinator import SkiResortDataUpdateCoordinator


class SkiResortEntity(CoordinatorEntity[SkiResortDataUpdateCoordinator]):
    """Base entity tied to a single resort (one HA device per resort)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize the entity and its device info."""
        super().__init__(coordinator)
        entry = coordinator.entry
        info = (coordinator.data or {}).get(DATA_INFO, {})
        friendly = entry.data.get(CONF_NAME) or entry.data[CONF_RESORT]
        region = info.get("region") or info.get("country")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=friendly,
            manufacturer=MANUFACTURER,
            model=region or "Ski resort",
            configuration_url=info.get("url"),
        )

    @property
    def _info(self) -> dict[str, Any]:
        """The resort's ``basicInfo`` block (name/region/coords/elevations)."""
        return (self.coordinator.data or {}).get(DATA_INFO, {})
