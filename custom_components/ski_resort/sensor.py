"""Sensor platform for the Ski Resort Forecast integration.

Per resort device:
  * snow: fresh snowfall, top depth (with trend), base depth, last-snow date
  * forecast: a 3-day summary sensor carrying the full 5-day payload as attrs
  * lifts (only when the option is on): open / total / % open counts

All entities are added once at platform setup; option changes reload the entry,
so toggling lift status re-runs setup and adds or drops those sensors.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkiResortConfigEntry
from .const import (
    CONF_ENABLE_LIFTS,
    CONF_UNITS,
    DATA_FORECAST,
    DATA_LIFTS,
    DATA_SNOW,
    DEFAULT_ENABLE_LIFTS,
    DEFAULT_UNITS,
    LENGTH_UNIT,
    SNOW_BASE,
    SNOW_FRESH,
    SNOW_LAST_DATE,
    SNOW_TOP,
    SNOW_TOP_CHANGE,
    SNOW_TOP_TREND,
)
from .coordinator import SkiResortDataUpdateCoordinator
from .entity import SkiResortEntity

# HA caps a state string at 255 chars; forecast summaries can run longer, so the
# state is truncated and the untouched text is kept in an attribute.
_MAX_STATE_LEN = 255


@dataclass(frozen=True, kw_only=True)
class SnowSensorDescription(SensorEntityDescription):
    """A snow sensor plus how to pull its value from the snow bundle."""

    value_fn: Callable[[dict[str, Any]], Any]
    length_unit: bool = False  # unit follows the imperial/metric option


SNOW_SENSORS: tuple[SnowSensorDescription, ...] = (
    SnowSensorDescription(
        key="fresh_snow",
        translation_key="fresh_snow",
        icon="mdi:snowflake",
        state_class=SensorStateClass.MEASUREMENT,
        length_unit=True,
        value_fn=lambda s: s.get(SNOW_FRESH),
    ),
    SnowSensorDescription(
        key="top_snow_depth",
        translation_key="top_snow_depth",
        icon="mdi:image-filter-hdr",
        state_class=SensorStateClass.MEASUREMENT,
        length_unit=True,
        value_fn=lambda s: s.get(SNOW_TOP),
    ),
    SnowSensorDescription(
        key="base_snow_depth",
        translation_key="base_snow_depth",
        icon="mdi:snowflake-variant",
        state_class=SensorStateClass.MEASUREMENT,
        length_unit=True,
        value_fn=lambda s: s.get(SNOW_BASE),
    ),
    SnowSensorDescription(
        key="last_snow_date",
        translation_key="last_snow_date",
        icon="mdi:calendar",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda s: s.get(SNOW_LAST_DATE),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkiResortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for a resort config entry."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        SkiResortSnowSensor(coordinator, desc) for desc in SNOW_SENSORS
    ]
    entities.append(SkiResortForecastSensor(coordinator))

    if entry.options.get(CONF_ENABLE_LIFTS, DEFAULT_ENABLE_LIFTS) and entry.options.get(
        "lift_slug"
    ):
        entities.extend(
            (
                SkiResortLiftSensor(coordinator, "lifts_open", "open"),
                SkiResortLiftSensor(coordinator, "lifts_total", "total"),
                SkiResortLiftPercentSensor(coordinator),
            )
        )

    async_add_entities(entities)


class SkiResortSnowSensor(SkiResortEntity, SensorEntity):
    """A single snow measurement/date sensor."""

    entity_description: SnowSensorDescription

    def __init__(
        self,
        coordinator: SkiResortDataUpdateCoordinator,
        description: SnowSensorDescription,
    ) -> None:
        """Initialize the snow sensor, resolving its unit from the option."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
        if description.length_unit:
            units = coordinator.entry.options.get(CONF_UNITS, DEFAULT_UNITS)
            self._attr_native_unit_of_measurement = LENGTH_UNIT.get(units, "in")

    @property
    def _snow(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(DATA_SNOW, {})

    @property
    def native_value(self) -> float | date | None:
        """The sensor's current value from the shaped snow bundle."""
        return self.entity_description.value_fn(self._snow)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the top-depth trend on the top-depth sensor only."""
        if self.entity_description.key != "top_snow_depth":
            return None
        snow = self._snow
        return {
            "trend": snow.get(SNOW_TOP_TREND),
            "change": snow.get(SNOW_TOP_CHANGE),
        }


class SkiResortForecastSensor(SkiResortEntity, SensorEntity):
    """3-day forecast summary; the full 5-day payload rides as attributes."""

    _attr_translation_key = "forecast_3day"
    _attr_icon = "mdi:weather-snowy"

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize the forecast summary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_forecast_3day"

    @property
    def _forecast(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(DATA_FORECAST, {})

    @property
    def native_value(self) -> str | None:
        """The 3-day summary text, truncated to HA's 255-char state limit."""
        summary = self._forecast.get("summary3Day")
        if not isinstance(summary, str):
            return None
        return summary if len(summary) <= _MAX_STATE_LEN else summary[:254] + "…"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Full summaries, the 5-day forecast, and resort metadata."""
        fc = self._forecast
        return {
            "summary_3day": fc.get("summary3Day"),
            "summary_5day": fc.get("summary5Day"),
            "forecast_5day": fc.get("forecast5Day"),
            "resort_info": self._info or None,
        }


class SkiResortLiftSensor(SkiResortEntity, SensorEntity):
    """A lift count sensor (open or total) from the conditions product."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gondola"

    def __init__(
        self,
        coordinator: SkiResortDataUpdateCoordinator,
        key: str,
        stat: str,
    ) -> None:
        """Initialize a lift-count sensor for the given stat key."""
        super().__init__(coordinator)
        self._stat = stat
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

    @property
    def _lifts(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DATA_LIFTS)

    @property
    def available(self) -> bool:
        """Available only when the lift section returned usable data."""
        return super().available and self._lifts is not None

    @property
    def native_value(self) -> int | None:
        """The requested lift stat, or ``None`` when lifts are unavailable."""
        lifts = self._lifts
        return lifts.get(self._stat) if lifts else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Break the other statuses out as attributes on the open sensor."""
        lifts = self._lifts
        if not lifts or self._stat != "open":
            return None
        return {
            "hold": lifts.get("hold"),
            "scheduled": lifts.get("scheduled"),
            "closed": lifts.get("closed"),
            "total": lifts.get("total"),
        }


class SkiResortLiftPercentSensor(SkiResortEntity, SensorEntity):
    """Percentage of lifts open, from the conditions product's stats block."""

    _attr_translation_key = "lifts_open_percent"
    _attr_icon = "mdi:percent"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize the percent-open sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_lifts_open_percent"

    @property
    def _lifts(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DATA_LIFTS)

    @property
    def available(self) -> bool:
        """Available only when a numeric open-percentage is present."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> int | None:
        """The open percentage from ``stats.percentage.open`` if numeric."""
        lifts = self._lifts
        if not lifts:
            return None
        pct = lifts.get("percentage")
        if not isinstance(pct, dict):
            return None
        value = pct.get("open")
        return value if isinstance(value, (int, float)) else None
