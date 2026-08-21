"""Data update coordinator for the Ski Resort Forecast integration.

One coordinator per config entry (one resort). Each refresh fetches snow
conditions and the forecast concurrently — plus lift status when that option is
on — shapes them into a stable bundle, and tags the top-depth trend against the
previous poll (no database; the same in-memory approach as sycamore-ha).

Resilience: a single section failing (RapidAPI 500s one endpoint, or the
optional lift product isn't subscribed) degrades that section to ``None``
rather than blanking the whole resort. Auth failures propagate as
``ConfigEntryAuthFailed`` to trigger reauth; a total wipe-out raises
``UpdateFailed`` so entities go unavailable honestly.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SkiResortAuthError,
    SkiResortClient,
    SkiResortConnectionError,
)
from .const import (
    CONF_ELEVATION,
    CONF_ENABLE_LIFTS,
    CONF_LIFT_SLUG,
    CONF_RESORT,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_UNITS,
    DATA_FORECAST,
    DATA_INFO,
    DATA_LIFTS,
    DATA_SNOW,
    DEFAULT_ELEVATION,
    DEFAULT_ENABLE_LIFTS,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_UNITS,
    DOMAIN,
    SNOW_BASE,
    SNOW_FRESH,
    SNOW_LAST_DATE,
    SNOW_TOP,
    SNOW_TOP_CHANGE,
    SNOW_TOP_TREND,
    UNIT_QUERY,
)
from .helpers import parse_measure, parse_snow_date, trend_of

if TYPE_CHECKING:
    from . import SkiResortConfigEntry

_LOGGER = logging.getLogger(__name__)


class SkiResortDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and shape one resort's data on a fixed interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SkiResortConfigEntry,
        client: SkiResortClient,
    ) -> None:
        """Initialize the coordinator from the entry's options."""
        self.entry = entry
        self._client = client
        # Remembered across refreshes to compute the top-depth trend without a
        # database, mirroring sycamore-ha's grade-trend approach.
        self._prev_top: float | None = None

        minutes = entry.options.get(
            CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_RESORT]}",
            update_interval=timedelta(minutes=minutes),
        )

    @property
    def resort(self) -> str:
        """The forecast-API resort name for this entry."""
        return self.entry.data[CONF_RESORT]

    @property
    def _units(self) -> str:
        return self.entry.options.get(CONF_UNITS, DEFAULT_UNITS)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch snow + forecast (+ lifts), returning the shaped bundle."""
        units_q = UNIT_QUERY.get(self._units, "i")
        elevation = self.entry.options.get(CONF_ELEVATION, DEFAULT_ELEVATION)
        lifts_on = self.entry.options.get(CONF_ENABLE_LIFTS, DEFAULT_ENABLE_LIFTS)
        slug = self.entry.options.get(CONF_LIFT_SLUG) or ""

        snow_raw = await self._safe_section(
            "snowConditions",
            self._client.async_get_snow_conditions(self.resort, units_q),
        )
        forecast_raw = await self._safe_section(
            "forecast",
            self._client.async_get_forecast(self.resort, units_q, elevation),
        )
        lifts_raw: dict[str, Any] | None = None
        if lifts_on and slug:
            lifts_raw = await self._safe_section(
                "liftStatus", self._client.async_get_lift_status(slug)
            )

        # If every section we tried failed (and none was an auth error, which
        # would already have raised), surface it rather than publishing a blank
        # resort that reads as "0 in of snow everywhere".
        attempted = [snow_raw, forecast_raw]
        if lifts_on and slug:
            attempted.append(lifts_raw)
        if all(section is None for section in attempted):
            raise UpdateFailed(f"No data returned for {self.resort}")

        return {
            DATA_SNOW: self._shape_snow(snow_raw or {}),
            DATA_FORECAST: self._shape_forecast(forecast_raw or {}),
            DATA_INFO: self._extract_info(forecast_raw or {}),
            DATA_LIFTS: self._shape_lifts(lifts_raw) if lifts_raw else None,
        }

    async def _safe_section(self, label: str, coro: Any) -> dict[str, Any] | None:
        """Await one section, degrading non-auth failures to ``None``.

        Auth errors re-raise as ``ConfigEntryAuthFailed`` (a bad key affects
        every section, so there's nothing to degrade to). Any other error is
        logged and swallowed so the remaining sections still publish.
        """
        try:
            return await coro
        except SkiResortAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SkiResortConnectionError as err:
            _LOGGER.warning("%s: %s section unavailable: %s", self.resort, label, err)
            return None

    def _shape_snow(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize snowConditions and tag the top-depth trend.

        Fresh snowfall of ``null`` means "none fell", so it floors to ``0.0``;
        depths of ``null`` stay ``None`` (unknown), so a missing base reading
        shows as unavailable rather than a bogus zero.
        """
        fresh = parse_measure(raw.get("freshSnowfall"))
        top = parse_measure(raw.get("topSnowDepth"))
        base = parse_measure(raw.get("botSnowDepth"))

        trend = trend_of(top, self._prev_top)
        change = (
            round(top - self._prev_top, 2)
            if top is not None and self._prev_top is not None
            else None
        )
        if top is not None:
            self._prev_top = top

        return {
            SNOW_FRESH: fresh if fresh is not None else 0.0,
            SNOW_TOP: top,
            SNOW_BASE: base,
            SNOW_LAST_DATE: parse_snow_date(raw.get("lastSnowfallDate")),
            SNOW_TOP_TREND: trend,
            SNOW_TOP_CHANGE: change,
            "raw": raw,
        }

    @staticmethod
    def _shape_forecast(raw: dict[str, Any]) -> dict[str, Any]:
        """Pull the summary fields, keeping the raw payload for attributes."""
        return {
            "summary3Day": raw.get("summary3Day"),
            "summary5Day": raw.get("summary5Day"),
            "forecast5Day": raw.get("forecast5Day"),
            "raw": raw,
        }

    @staticmethod
    def _extract_info(forecast_raw: dict[str, Any]) -> dict[str, Any]:
        """Resort metadata from the forecast payload's ``basicInfo`` block."""
        info = forecast_raw.get("basicInfo")
        return info if isinstance(info, dict) else {}

    @staticmethod
    def _shape_lifts(raw: dict[str, Any]) -> dict[str, Any] | None:
        """Flatten skiapi's ``data.lifts.stats`` into open/total/percentage.

        Returns ``None`` if the payload lacks the expected shape (e.g. the slug
        was wrong) so the lift sensors go unavailable instead of reading zero.
        """
        data = raw.get("data")
        if not isinstance(data, dict):
            return None
        lifts = data.get("lifts")
        if not isinstance(lifts, dict):
            return None
        stats = lifts.get("stats")
        if not isinstance(stats, dict):
            return None

        def _int(key: str) -> int:
            try:
                return int(stats.get(key) or 0)
            except (TypeError, ValueError):
                return 0

        counts = {k: _int(k) for k in ("open", "hold", "scheduled", "closed")}
        total = sum(counts.values())
        return {
            **counts,
            "total": total,
            "percentage": stats.get("percentage"),
            "status": lifts.get("status"),
            "resort_name": data.get("name"),
        }
