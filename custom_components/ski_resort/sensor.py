"""Sensor platform for the Ski Resort integration.

Groups:
  * Weather/snow (Open-Meteo): fresh snowfall (24h), snow depth, freezing level,
    temperature, wind.
  * Terrain (OpenSkiMap, static): lift count, run count, vertical drop, summit /
    base elevation — with per-type and per-difficulty breakdowns as attributes.
  * Live lifts (Liftie/skiapi, optional): lifts open + % open.
  * Reported snow (RapidAPI snow-forecast, optional): base/summit depth, fresh
    snow, last snowfall date.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkiResortConfigEntry
from .const import (
    CONF_ENABLE_AVALANCHE,
    CONF_FORECAST_RESORT,
    CONF_LIFT_SLUG,
    CONF_LIFTIE_BASE_URL,
    CONF_RAPIDAPI_KEY,
    DATA_ALERTS,
    DATA_AVALANCHE,
    DATA_INFO,
    DATA_LIFTS,
    DATA_SNOW,
    DATA_WEATHER,
    DEPTH_UNIT,
    ELEV_UNIT,
    LENGTH_UNIT,
    OPENSKIMAP_PERMALINK,
    PRECIP_UNIT,
    SKIMAP_PERMALINK,
    SNOW_FORECAST_DAYS,
    UNIT_IMPERIAL,
    UNIT_METRIC,
    WIKIDATA_PERMALINK,
    WX_APPARENT,
    WX_DAILY,
    WX_FREEZING_LEVEL,
    WX_FRESH_SNOW,
    WX_PRECIP,
    WX_SNOW_DEPTH,
    WX_TEMP,
    WX_WIND,
)
from .coordinator import SkiResortDataUpdateCoordinator
from .entity import SkiResortEntity
from .helpers import (
    alert_attributes,
    cm_to_display,
    m_to_depth_display,
    m_to_elev_display,
    mm_to_display,
)

PARALLEL_UPDATES = 0

async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkiResortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all sensors for a ski area."""
    coordinator = entry.runtime_data
    imperial = coordinator.imperial
    length = LENGTH_UNIT[UNIT_IMPERIAL if imperial else UNIT_METRIC]
    depth = DEPTH_UNIT[UNIT_IMPERIAL if imperial else UNIT_METRIC]
    elev = ELEV_UNIT[UNIT_IMPERIAL if imperial else UNIT_METRIC]

    entities: list[SensorEntity] = [
        # --- Open-Meteo weather/snow ---
        SkiResortWeatherSensor(
            coordinator, "fresh_snow", length,
            lambda w: cm_to_display(w.get(WX_FRESH_SNOW), imperial),
            icon="mdi:snowflake", state_class=SensorStateClass.MEASUREMENT,
        ),
        # No PRECIPITATION device class on purpose: it would make HA convert the
        # value to its own unit system, overriding this integration's imperial/
        # metric option (the other weather sensors omit it for the same reason).
        SkiResortWeatherSensor(
            coordinator, "precipitation_24h",
            PRECIP_UNIT[UNIT_IMPERIAL if imperial else UNIT_METRIC],
            lambda w: mm_to_display(w.get(WX_PRECIP), imperial),
            icon="mdi:weather-rainy",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SkiResortWeatherSensor(
            coordinator, "snow_depth", depth,
            lambda w: m_to_depth_display(w.get(WX_SNOW_DEPTH), imperial),
            icon="mdi:snowflake-variant", state_class=SensorStateClass.MEASUREMENT,
        ),
        SkiResortWeatherSensor(
            coordinator, "freezing_level", elev,
            lambda w: m_to_elev_display(w.get(WX_FREEZING_LEVEL), imperial),
            icon="mdi:thermometer-water", state_class=SensorStateClass.MEASUREMENT,
        ),
        SkiResortWeatherSensor(
            coordinator, "temperature", UnitOfTemperature.CELSIUS,
            lambda w: w.get(WX_TEMP),
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SkiResortWeatherSensor(
            coordinator, "feels_like", UnitOfTemperature.CELSIUS,
            lambda w: w.get(WX_APPARENT),
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SkiResortWeatherSensor(
            coordinator, "wind_speed", UnitOfSpeed.KILOMETERS_PER_HOUR,
            lambda w: w.get(WX_WIND),
            device_class=SensorDeviceClass.WIND_SPEED,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SkiResortSnowForecastSensor(coordinator, length, imperial),
        # --- Terrain (static OpenSkiMap) ---
        SkiResortLiftCountSensor(coordinator),
        SkiResortRunCountSensor(coordinator),
        SkiResortElevationSensor(
            coordinator, "vertical_drop", elev, imperial,
            lambda a: (vmax - vmin)
            if (vmax := a.get("vMax")) is not None
            and (vmin := a.get("vMin")) is not None
            else None,
            icon="mdi:arrow-expand-vertical",
        ),
        SkiResortElevationSensor(
            coordinator, "summit_elevation", elev, imperial,
            lambda a: a.get("vMax"), icon="mdi:image-filter-hdr",
        ),
        SkiResortElevationSensor(
            coordinator, "base_elevation", elev, imperial,
            lambda a: a.get("vMin"), icon="mdi:terrain",
        ),
        SkiResortInfoSensor(coordinator),
    ]

    # --- Live lifts (optional) ---
    opts = entry.options
    if opts.get(CONF_LIFT_SLUG) and (
        opts.get(CONF_LIFTIE_BASE_URL) or opts.get(CONF_RAPIDAPI_KEY)
    ):
        entities.append(SkiResortLiftsOpenSensor(coordinator))
        entities.append(SkiResortLiftsPercentSensor(coordinator))

    # --- NWS weather alert (on by default, US resorts only) ---
    if coordinator.alerts_enabled:
        entities.append(SkiResortWeatherAlertSensor(coordinator))

    # --- Avalanche danger (optional) ---
    if opts.get(CONF_ENABLE_AVALANCHE):
        entities.append(SkiResortAvalancheSensor(coordinator))

    # --- Reported snow (RapidAPI, optional) ---
    if opts.get(CONF_RAPIDAPI_KEY) and opts.get(CONF_FORECAST_RESORT):
        entities.extend(
            (
                SkiResortReportedSnowSensor(coordinator, "reported_summit_depth",
                                            depth, lambda s: s.get("top")),
                SkiResortReportedSnowSensor(coordinator, "reported_base_depth",
                                            depth, lambda s: s.get("base")),
                SkiResortReportedSnowSensor(coordinator, "reported_fresh_snow",
                                            length, lambda s: s.get("fresh")),
                SkiResortLastSnowDateSensor(coordinator),
            )
        )

    async_add_entities(entities)


class SkiResortWeatherSensor(SkiResortEntity, SensorEntity):
    """A weather/snow sensor read from the Open-Meteo bundle."""

    def __init__(
        self,
        coordinator: SkiResortDataUpdateCoordinator,
        key: str,
        unit: str,
        value_fn: Callable[[dict[str, Any]], Any],
        *,
        icon: str | None = None,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
    ) -> None:
        """Initialize the weather sensor."""
        super().__init__(coordinator)
        self._value_fn = value_fn
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def _weather(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DATA_WEATHER)

    @property
    def available(self) -> bool:
        """Available only when Open-Meteo returned data."""
        return super().available and self._weather is not None

    @property
    def native_value(self) -> Any:
        """Value from the weather bundle."""
        return self._value_fn(self._weather or {})


class SkiResortSnowForecastSensor(SkiResortEntity, SensorEntity):
    """Snowfall over the next few days (Open-Meteo daily forecast).

    State is the total forecast snowfall over the next ``SNOW_FORECAST_DAYS``
    days; the per-day breakdown (``[{date, snowfall}, ...]``) is exposed as the
    ``daily`` attribute so dashboards and the TRMNL screen can render each day.
    """

    _attr_translation_key = "snow_forecast"
    _attr_icon = "mdi:snowflake"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: SkiResortDataUpdateCoordinator,
        unit: str,
        imperial: bool,
    ) -> None:
        """Initialize the snow-forecast sensor."""
        super().__init__(coordinator)
        self._imperial = imperial
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{coordinator.entry.entry_id}_snow_forecast"

    @property
    def _weather(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DATA_WEATHER)

    @property
    def _days(self) -> list[dict[str, Any]]:
        """The next ``SNOW_FORECAST_DAYS`` daily-forecast entries."""
        return ((self._weather or {}).get(WX_DAILY) or [])[:SNOW_FORECAST_DAYS]

    @property
    def available(self) -> bool:
        """Available only when Open-Meteo returned a forecast."""
        return super().available and self._weather is not None

    @property
    def native_value(self) -> float | None:
        """Total snowfall (display units) over the next few days."""
        values = [
            v
            for day in self._days
            if (v := cm_to_display(day.get("snowfall_cm"), self._imperial)) is not None
        ]
        return round(sum(values), 1) if values else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Per-day snowfall and liquid precipitation, one entry per forecast day.

        The ``precipitation`` figure makes a warm, wet forecast legible: a day
        can show meaningful precipitation with little or no snowfall (rain, or
        snow only above the freezing level), which otherwise reads as a
        contradiction against the moisture people can see coming.
        """
        return {
            "daily": [
                {
                    "date": day.get("datetime"),
                    "snowfall": cm_to_display(day.get("snowfall_cm"), self._imperial),
                    "precipitation": mm_to_display(
                        day.get("precipitation"), self._imperial
                    ),
                }
                for day in self._days
            ]
        }


class SkiResortLiftCountSensor(SkiResortEntity, SensorEntity):
    """Total lift count from OpenSkiMap (with per-type breakdown)."""

    _attr_translation_key = "lift_count"
    _attr_icon = "mdi:gondola"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_lift_count"

    @property
    def native_value(self) -> int | None:
        """OpenSkiMap total lift count."""
        return self.area.get("lifts")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Per-type lift breakdown."""
        return {"by_type": self.area.get("liftTypes") or {}}


class SkiResortRunCountSensor(SkiResortEntity, SensorEntity):
    """Total run count from OpenSkiMap (with per-difficulty breakdown)."""

    _attr_translation_key = "run_count"
    _attr_icon = "mdi:ski"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_run_count"

    @property
    def native_value(self) -> int | None:
        """OpenSkiMap total run count."""
        return self.area.get("runs")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Per-difficulty counts, total run length, snowmaking length."""
        return {
            "by_difficulty": self.area.get("byDiff") or {},
            "run_km": self.area.get("runKm"),
            "snowmaking_km": self.area.get("snowKm"),
        }


class SkiResortElevationSensor(SkiResortEntity, SensorEntity):
    """A static elevation figure from OpenSkiMap, converted to ft/m."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: SkiResortDataUpdateCoordinator,
        key: str,
        unit: str,
        imperial: bool,
        value_fn: Callable[[dict[str, Any]], float | None],
        *,
        icon: str | None = None,
    ) -> None:
        """Initialize the elevation sensor."""
        super().__init__(coordinator)
        self._value_fn = value_fn
        self._imperial = imperial
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon

    @property
    def native_value(self) -> float | None:
        """Converted elevation value."""
        return m_to_elev_display(self._value_fn(self.area), self._imperial)


class SkiResortLiftsOpenSensor(SkiResortEntity, SensorEntity):
    """Live count of open lifts (Liftie/skiapi)."""

    _attr_translation_key = "lifts_open"
    _attr_icon = "mdi:gondola"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_lifts_open"

    @property
    def _lifts(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DATA_LIFTS)

    @property
    def available(self) -> bool:
        """Available only when live lift data was returned."""
        return super().available and self._lifts is not None

    @property
    def native_value(self) -> int | None:
        """Number of open lifts."""
        lifts = self._lifts
        return lifts.get("open") if lifts else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Other lift states, total, and source."""
        lifts = self._lifts
        if not lifts:
            return None
        return {
            "hold": lifts.get("hold"),
            "scheduled": lifts.get("scheduled"),
            "closed": lifts.get("closed"),
            "total": lifts.get("total"),
            "source": lifts.get("source"),
        }


class SkiResortLiftsPercentSensor(SkiResortEntity, SensorEntity):
    """Percentage of lifts open (open / OpenSkiMap total)."""

    _attr_translation_key = "lifts_open_percent"
    _attr_icon = "mdi:percent"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_lifts_open_percent"

    @property
    def _lifts(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DATA_LIFTS)

    @property
    def available(self) -> bool:
        """Available only when a percentage could be computed."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> int | None:
        """Percent open."""
        lifts = self._lifts
        return lifts.get("percentage") if lifts else None


class SkiResortReportedSnowSensor(SkiResortEntity, SensorEntity):
    """A depth/snow value reported by the optional RapidAPI snow-forecast."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:snowflake-alert"

    def __init__(
        self,
        coordinator: SkiResortDataUpdateCoordinator,
        key: str,
        unit: str,
        value_fn: Callable[[dict[str, Any]], Any],
    ) -> None:
        """Initialize the reported-snow sensor."""
        super().__init__(coordinator)
        self._value_fn = value_fn
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit

    @property
    def _snow(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DATA_SNOW)

    @property
    def available(self) -> bool:
        """Available only when the RapidAPI snow section returned data."""
        return super().available and self._snow is not None

    @property
    def native_value(self) -> Any:
        """Reported value."""
        return self._value_fn(self._snow or {})


class SkiResortLastSnowDateSensor(SkiResortEntity, SensorEntity):
    """Last snowfall date reported by the RapidAPI snow-forecast."""

    _attr_translation_key = "last_snow_date"
    _attr_icon = "mdi:calendar"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_last_snow_date"

    @property
    def _snow(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DATA_SNOW)

    @property
    def available(self) -> bool:
        """Available only when the RapidAPI snow section returned data."""
        return super().available and self._snow is not None

    @property
    def native_value(self) -> date | None:
        """The last snowfall date."""
        snow = self._snow
        return snow.get("last_snow_date") if snow else None


class SkiResortInfoSensor(SkiResortEntity, SensorEntity):
    """Diagnostic sensor: resort status + metadata links and facts."""

    _attr_translation_key = "resort_info"
    _attr_icon = "mdi:information-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize the resort-info sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_resort_info"

    @property
    def _info(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(DATA_INFO) or {}

    @property
    def native_value(self) -> str | None:
        """The OpenSkiMap operating status."""
        return self.area.get("status")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Region, links, and enrichment facts."""
        area = self.area
        info = self._info
        attrs: dict[str, Any] = {
            "country": area.get("country"),
            "region": area.get("region"),
            "latitude": area.get("lat"),
            "longitude": area.get("lon"),
            "website": info.get("website") or area.get("web"),
            "openskimap_url": OPENSKIMAP_PERMALINK.format(id=area.get("id")),
        }
        if info.get("opening_year"):
            attrs["opening_year"] = info["opening_year"]
        if area.get("wd"):
            attrs["wikidata_url"] = WIKIDATA_PERMALINK.format(id=area["wd"])
        if area.get("sk") is not None:
            attrs["skimap_url"] = SKIMAP_PERMALINK.format(id=area["sk"])
        return attrs


class SkiResortWeatherAlertSensor(SkiResortEntity, SensorEntity):
    """Human-readable NWS weather alert for the resort (US only).

    Companion to the ``weather_alert`` binary sensor: where that answers "is any
    alert active?" (on/off) for automations, this sensor's *state* is the most
    significant active alert's event name (e.g. "Flood Watch"), or "None" when
    clear — so a dashboard shows what the alert is, not just "Unsafe". The full
    headline, description, and instruction ride along as attributes.
    """

    _attr_translation_key = "weather_alert"
    _attr_icon = "mdi:alert"

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_active_alert"

    @property
    def _alerts(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DATA_ALERTS)

    @property
    def available(self) -> bool:
        """Available only when the NWS query returned (even with zero alerts)."""
        return super().available and self._alerts is not None

    @property
    def native_value(self) -> str | None:
        """The top alert's event name, or "None" when nothing is active."""
        alerts = self._alerts
        if not alerts:
            return None
        items = alerts.get("alerts") or []
        return items[0].get("event") if items else "None"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Detail of the most significant alert plus a compact list."""
        return alert_attributes(self._alerts)


class SkiResortAvalancheSensor(SkiResortEntity, SensorEntity):
    """Avalanche danger rating for the resort's forecast zone (avalanche.org).

    State is the danger word (e.g. "considerable"); the numeric level, zone,
    travel advice, expiry, and forecast link are attributes.
    """

    _attr_translation_key = "avalanche_danger"
    _attr_icon = "mdi:alert"
    _attr_device_class = SensorDeviceClass.ENUM
    # North American public avalanche danger scale (avalanche.org `danger`).
    _attr_options = [
        "no rating",
        "low",
        "moderate",
        "considerable",
        "high",
        "extreme",
    ]

    def __init__(self, coordinator: SkiResortDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_avalanche_danger"

    @property
    def _avalanche(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(DATA_AVALANCHE)

    @property
    def available(self) -> bool:
        """Available only when a forecast zone was matched."""
        return super().available and self._avalanche is not None

    @property
    def native_value(self) -> str | None:
        """The danger rating word, restricted to the documented enum options."""
        av = self._avalanche
        rating = av.get("rating") if av else None
        return rating if rating in self._attr_options else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Danger level, zone, advice, expiry, and forecast link."""
        av = self._avalanche
        if not av:
            return None
        return {
            "level": av.get("level"),
            "zone": av.get("zone"),
            "center": av.get("center"),
            "travel_advice": av.get("advice"),
            "expires": av.get("expires"),
            "warning": av.get("warning"),
            "forecast_url": av.get("link"),
        }
