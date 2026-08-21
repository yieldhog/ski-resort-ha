"""Base entity for the Ski Resort integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_NAME,
    DOMAIN,
    MANUFACTURER,
    OPENSKIMAP_PERMALINK,
)
from .coordinator import SkiResortDataUpdateCoordinator


class SkiResortEntity(CoordinatorEntity[SkiResortDataUpdateCoordinator]):
    """Base entity for one OpenSkiMap ski area (one HA device per area)."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize device info from the OpenSkiMap area record."""
        super().__init__(coordinator)
        area = coordinator.area
        entry = coordinator.entry
        region = area.get("region") or area.get("country")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME) or area.get("name"),
            manufacturer=MANUFACTURER,
            model=region or "Ski area",
            configuration_url=OPENSKIMAP_PERMALINK.format(id=area.get("id")),
        )

    @property
    def area(self) -> dict[str, Any]:
        """The bundled OpenSkiMap area record."""
        return self.coordinator.area
