"""Weather platform: a per-resort weather entity backed by Open-Meteo."""

from __future__ import annotations

from typing import Any

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import SkiResortConfigEntry
from .const import (
    DATA_WEATHER,
    WX_APPARENT,
    WX_CONDITION,
    WX_DAILY,
    WX_GUST,
    WX_HUMIDITY,
    WX_TEMP,
    WX_WIND,
)
from .coordinator import SkiResortDataUpdateCoordinator
from .entity import SkiResortEntity
from .helpers import day_start_iso

PARALLEL_UPDATES = 0


def _forecast_datetime(day_value: Any, utc_offset_seconds: Any) -> Any:
    """Return a full ISO datetime for a daily forecast's date.

    HA reads a bare ``YYYY-MM-DD`` as UTC midnight, mislabelling the day west of
    UTC. Anchor it to the resort's local midnight using Open-Meteo's offset; if
    that offset is missing, fall back to the HA time zone's local midnight.
    """
    anchored = day_start_iso(day_value, utc_offset_seconds)
    if anchored is not None:
        return anchored
    parsed = dt_util.parse_date(day_value) if isinstance(day_value, str) else None
    return dt_util.start_of_local_day(parsed).isoformat() if parsed else day_value

async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkiResortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the resort weather entity."""
    async_add_entities([SkiResortWeather(entry.runtime_data)])


class SkiResortWeather(SkiResortEntity, WeatherEntity):
    """Open-Meteo-backed weather for a ski area (native SI units)."""

    _attr_name = None  # use the device (resort) name
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize the weather entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_weather"

    @property
    def _weather(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(DATA_WEATHER) or {}

    @property
    def available(self) -> bool:
        """Available only when Open-Meteo returned data."""
        return super().available and bool(self._weather)

    @property
    def condition(self) -> str | None:
        """Current condition (HA vocabulary)."""
        return self._weather.get(WX_CONDITION)

    @property
    def native_temperature(self) -> float | None:
        """Current temperature (°C)."""
        return self._weather.get(WX_TEMP)

    @property
    def native_apparent_temperature(self) -> float | None:
        """Current apparent ("feels like") temperature (°C)."""
        return self._weather.get(WX_APPARENT)

    @property
    def native_wind_speed(self) -> float | None:
        """Current wind speed (km/h)."""
        return self._weather.get(WX_WIND)

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Current wind gust (km/h)."""
        return self._weather.get(WX_GUST)

    @property
    def humidity(self) -> float | None:
        """Relative humidity (%)."""
        return self._weather.get(WX_HUMIDITY)

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast built from Open-Meteo."""
        days = self._weather.get(WX_DAILY) or []
        offset = (self._weather.get("raw") or {}).get("utc_offset_seconds")
        forecast: list[Forecast] = []
        for day in days:
            forecast.append(
                Forecast(
                    datetime=_forecast_datetime(day.get("datetime"), offset),
                    condition=day.get("condition"),
                    native_temperature=day.get("temperature"),
                    native_templow=day.get("templow"),
                    native_apparent_temperature=day.get("apparent_temperature"),
                    native_wind_speed=day.get("wind_speed"),
                    native_precipitation=day.get("precipitation"),
                )
            )
        return forecast or None
