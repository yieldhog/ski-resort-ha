"""Data update coordinator for the Ski Resort integration.

One coordinator per config entry (one OpenSkiMap ski area). Each refresh always
fetches free Open-Meteo weather/snow for the area's coordinates, and optionally
live lift status (self-hosted Liftie or RapidAPI skiapi) and a RapidAPI
snow-forecast summary. Optional sources degrade to ``None`` on failure — only a
total wipe-out (even Open-Meteo failing) raises ``UpdateFailed``. Nothing here
requires an API key, so there is no reauth flow.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    SkiResortError,
    async_liftie,
    async_open_meteo,
    async_rapidapi_snow,
    async_skiapi,
    async_skimap_trailmap,
    async_wikidata_item,
)
from .const import (
    CONF_AREA,
    CONF_FORECAST_RESORT,
    CONF_LIFT_SLUG,
    CONF_LIFTIE_BASE_URL,
    CONF_RAPIDAPI_KEY,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_UNITS,
    DATA_AREA,
    DATA_INFO,
    DATA_LIFTS,
    DATA_SNOW,
    DATA_WEATHER,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_UNITS,
    DOMAIN,
    UNIT_IMPERIAL,
    WX_CONDITION,
    WX_DAILY,
    WX_FREEZING_LEVEL,
    WX_FRESH_SNOW,
    WX_GUST,
    WX_HUMIDITY,
    WX_SNOW_DEPTH,
    WX_TEMP,
    WX_WIND,
)
from .helpers import (
    condition_from_wmo,
    local_now_marker,
    parse_measure,
    parse_snow_date,
    sum_next_hours,
    value_at_hour,
)

if TYPE_CHECKING:
    from . import SkiResortConfigEntry

_LOGGER = logging.getLogger(__name__)


class SkiResortDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and shape one ski area's weather, snow, and lift data."""

    def __init__(self, hass: HomeAssistant, entry: SkiResortConfigEntry) -> None:
        """Initialize the coordinator from the entry's area + options."""
        self.entry = entry
        self.area: dict[str, Any] = entry.data[CONF_AREA]
        self._prev_depth: float | None = None
        self._info: dict[str, Any] | None = None
        minutes = entry.options.get(
            CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.area.get('name')}",
            update_interval=timedelta(minutes=minutes),
        )

    @property
    def imperial(self) -> bool:
        """Whether display units are imperial."""
        return bool(self.entry.options.get(CONF_UNITS, DEFAULT_UNITS) == UNIT_IMPERIAL)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch every section concurrently; each degrades independently.

        Weather, snow, lifts, and (once) enrichment run in parallel so one slow
        or failing source can't hold up or blank the others. Only a total
        wipe-out of the live sections raises ``UpdateFailed``.
        """
        opts = self.entry.options
        lat, lon = self.area.get("lat"), self.area.get("lon")
        key = opts.get(CONF_RAPIDAPI_KEY)
        forecast_resort = opts.get(CONF_FORECAST_RESORT)

        jobs: dict[str, Any] = {}
        if lat is not None and lon is not None:
            jobs[DATA_WEATHER] = self._fetch_weather(lat, lon)
        if key and forecast_resort:
            jobs[DATA_SNOW] = self._fetch_rapidapi_snow(key, forecast_resort)
        jobs[DATA_LIFTS] = self._fetch_lifts()
        if self._info is None:
            jobs[DATA_INFO] = self._fetch_info()

        names = list(jobs)
        results = await asyncio.gather(*(self._safe(n, jobs[n]) for n in names))
        data = dict(zip(names, results, strict=True))

        if DATA_INFO in data and data[DATA_INFO] is not None:
            # Cache only a completed enrichment (``_fetch_info`` returns ``None``
            # on a transient failure); leaving ``self._info`` unset means the
            # next poll retries instead of latching an empty result forever.
            self._info = data[DATA_INFO]

        weather = data.get(DATA_WEATHER)
        snow = data.get(DATA_SNOW)
        lifts = data.get(DATA_LIFTS)
        if weather is None and snow is None and lifts is None:
            raise UpdateFailed(f"No data available for {self.area.get('name')}")

        return {
            DATA_WEATHER: weather,
            DATA_SNOW: snow,
            DATA_LIFTS: lifts,
            DATA_AREA: self.area,
            DATA_INFO: self._info or {},
        }

    async def _safe(self, label: str, coro: Any) -> Any:
        """Await a section, degrading any client failure to ``None``.

        Catches the whole ``SkiResortError`` hierarchy — including auth errors
        from an invalid RapidAPI key — because every network source here is
        optional; the core (Open-Meteo) needs no key, so nothing should ever
        raise ``ConfigEntryAuthFailed`` or blank the entire integration.
        """
        try:
            return await coro
        except SkiResortError as err:
            _LOGGER.warning(
                "%s: %s unavailable: %s", self.area.get("name"), label, err
            )
            return None

    # --- Weather (Open-Meteo) ---------------------------------------------
    async def _fetch_weather(self, lat: float, lon: float) -> dict[str, Any]:
        raw = await async_open_meteo(self.hass, lat, lon)
        current = raw.get("current") or {}
        hourly = raw.get("hourly") or {}
        daily = raw.get("daily") or {}

        # Align the hourly window to the resort's current local hour; Open-Meteo
        # arrays start at 00:00 today, so an unaligned read would total "today so
        # far" and snapshot midnight instead of now.
        times = hourly.get("time") or []
        now = local_now_marker(dt_util.utcnow(), raw.get("utc_offset_seconds"))
        fresh = sum_next_hours(times, hourly.get("snowfall") or [], 24, now)
        depth = value_at_hour(times, hourly.get("snow_depth") or [], now)
        freezing = value_at_hour(times, hourly.get("freezing_level_height") or [], now)

        return {
            WX_TEMP: current.get("temperature_2m"),
            WX_WIND: current.get("wind_speed_10m"),
            WX_GUST: current.get("wind_gusts_10m"),
            WX_HUMIDITY: current.get("relative_humidity_2m"),
            WX_CONDITION: condition_from_wmo(current.get("weather_code")),
            WX_FRESH_SNOW: fresh,  # cm, next 24h
            WX_SNOW_DEPTH: depth,  # metres
            WX_FREEZING_LEVEL: freezing,  # metres
            WX_DAILY: self._shape_daily(daily),
            "raw": raw,
        }

    @staticmethod
    def _shape_daily(daily: dict[str, Any]) -> list[dict[str, Any]]:
        """Build a per-day forecast list (SI units + snowfall_cm)."""
        times = daily.get("time") or []

        def at(key: str, i: int) -> Any:
            seq = daily.get(key) or []
            return seq[i] if i < len(seq) else None

        return [
            {
                "datetime": day,
                "condition": condition_from_wmo(at("weather_code", i)),
                "temperature": at("temperature_2m_max", i),
                "templow": at("temperature_2m_min", i),
                "wind_speed": at("wind_speed_10m_max", i),
                "precipitation": at("precipitation_sum", i),
                "snowfall_cm": at("snowfall_sum", i),
            }
            for i, day in enumerate(times)
        ]

    # --- RapidAPI snow-forecast (optional) --------------------------------
    async def _fetch_rapidapi_snow(self, key: str, resort: str) -> dict[str, Any]:
        units_q = "i" if self.imperial else "m"
        raw = await async_rapidapi_snow(self.hass, key, resort, units_q)
        return {
            "fresh": parse_measure(raw.get("freshSnowfall")),
            "top": parse_measure(raw.get("topSnowDepth")),
            "base": parse_measure(raw.get("botSnowDepth")),
            "last_snow_date": parse_snow_date(raw.get("lastSnowfallDate")),
            "raw": raw,
        }

    # --- Lifts (Liftie or skiapi) -----------------------------------------
    async def _fetch_lifts(self) -> dict[str, Any] | None:
        opts = self.entry.options
        slug = opts.get(CONF_LIFT_SLUG)
        if not slug:
            return None
        base_url = opts.get(CONF_LIFTIE_BASE_URL)
        key = opts.get(CONF_RAPIDAPI_KEY)
        if base_url:
            raw = await async_liftie(self.hass, base_url, slug)
            stats = ((raw.get("lifts") or {}).get("stats")) or {}
            source = "liftie"
        elif key:
            raw = await async_skiapi(self.hass, key, slug)
            stats = (
                ((raw.get("data") or {}).get("lifts") or {}).get("stats")
            ) or {}
            source = "skiapi"
        else:
            return None
        return self._shape_lifts(stats, source)

    def _shape_lifts(self, stats: dict[str, Any], source: str) -> dict[str, Any] | None:
        """Normalize lift stats; total prefers OpenSkiMap's authoritative count."""

        def as_int(key: str) -> int:
            try:
                return int(stats.get(key) or 0)
            except (TypeError, ValueError):
                return 0

        counts = {k: as_int(k) for k in ("open", "hold", "scheduled", "closed")}
        if not any(counts.values()) and "open" not in stats:
            return None
        reported_total = sum(counts.values())
        osm_total = self.area.get("lifts") or 0
        total = osm_total or reported_total
        # Clamp: Liftie's open count can briefly exceed OpenSkiMap's lift total
        # (e.g. a newly added lift OpenSkiMap hasn't mapped yet), which would
        # otherwise report >100% open.
        pct = min(100, round(counts["open"] / total * 100)) if total else None
        return {**counts, "total": total, "percentage": pct, "source": source}

    # --- Enrichment (Wikidata photo/facts + skimap trail map) --------------
    async def _fetch_info(self) -> dict[str, Any] | None:
        """Best-effort static enrichment; never raises (each part is optional).

        Returns the enrichment dict once fetching *completes* — even when the
        resort simply has nothing to enrich (an empty dict is a valid, cacheable
        result). Returns ``None`` if a transient network error stopped it from
        completing, so the coordinator retries on the next poll rather than
        caching an empty result forever. Parse errors (malformed Wikidata) are
        not transient, so they don't force a retry.
        """
        info: dict[str, Any] = {}
        completed = True
        wikidata_id = self.area.get("wd")
        if wikidata_id:
            try:
                item = await async_wikidata_item(self.hass, wikidata_id)
                info.update(self._parse_wikidata(item))
            except SkiResortError as err:
                _LOGGER.debug("Wikidata fetch failed for %s: %s", wikidata_id, err)
                completed = False
            except (KeyError, IndexError, TypeError, ValueError) as err:
                _LOGGER.debug("Wikidata parse failed for %s: %s", wikidata_id, err)
        skimap_id = self.area.get("sk")
        if skimap_id is not None:
            try:
                trail_map_url = await async_skimap_trailmap(self.hass, skimap_id)
                if trail_map_url:
                    info["trail_map_url"] = trail_map_url
            except SkiResortError as err:
                _LOGGER.debug("skimap enrichment failed for %s: %s", skimap_id, err)
                completed = False
        return info if completed else None

    @staticmethod
    def _parse_wikidata(item: dict[str, Any]) -> dict[str, Any]:
        """Pull the official website and opening year from a Wikidata item."""
        statements = item.get("statements") or {}
        out: dict[str, Any] = {}
        website = statements.get("P856")
        if website:
            out["website"] = website[0]["value"]["content"]
        inception = statements.get("P571")
        if inception:
            time = inception[0]["value"]["content"]["time"]  # "+2010-00-00T..."
            out["opening_year"] = int(time[1:5])
        return out
