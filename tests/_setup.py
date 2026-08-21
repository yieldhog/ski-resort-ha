"""Shared setup helper for the Ski Resort test suite."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ski_resort.const import (
    CONF_AREA,
    CONF_NAME,
    CONF_OPENSKIMAP_ID,
    CONF_UNITS,
    DOMAIN,
    UNIT_IMPERIAL,
)

AREA = {
    "id": "vailid", "name": "Vail", "country": "United States",
    "region": "Colorado", "cc": "US", "lat": 39.6, "lon": -106.35,
    "status": "operating", "lifts": 32,
    "liftTypes": {"chair_lift": 20, "gondola": 2},
    "runs": 241, "runKm": 204.9, "byDiff": {"easy": 45, "advanced": 110},
    "snowKm": 0.0, "vMin": 2451.7, "vMax": 3516.7,
    "web": "https://www.vail.com", "wd": "Q14685139", "sk": 507,
    "poly": True, "nordic": False,
}

WIKIDATA = {"statements": {
    "P18": [{"value": {"content": "Vail.jpg"}}],
    "P856": [{"value": {"content": "https://www.vail.com"}}],
    "P571": [{"value": {"content": {"time": "+1962-00-00T00:00:00Z"}}}],
}}
TRAIL_MAP_URL = "https://files.skimap.org/trailmap507"

OPEN_METEO = {
    "current": {
        "temperature_2m": -5.0, "relative_humidity_2m": 80, "weather_code": 73,
        "wind_speed_10m": 12.0, "wind_gusts_10m": 25.0, "snowfall": 0.7,
    },
    "hourly": {
        "time": [f"2026-01-25T{h:02d}:00" for h in range(24)],
        "snowfall": [1.0] * 24,
        "snow_depth": [1.2] * 24,
        "freezing_level_height": [2500.0] * 24,
    },
    "daily": {
        "time": ["2026-01-25", "2026-01-26"],
        "weather_code": [73, 3],
        "temperature_2m_max": [-2.0, -1.0],
        "temperature_2m_min": [-8.0, -7.0],
        "snowfall_sum": [12.0, 3.0],
        "precipitation_sum": [8.0, 2.0],
        "wind_speed_10m_max": [20.0, 15.0],
        "wind_gusts_10m_max": [40.0, 30.0],
        "sunrise": ["2026-01-25T07:20", "2026-01-26T07:19"],
        "sunset": ["2026-01-25T17:00", "2026-01-26T17:01"],
    },
}
LIFTIE = {"lifts": {"stats": {
    "open": 10, "hold": 1, "scheduled": 2, "closed": 3,
    "percentage": {"open": 63},
}}}
SKIAPI = {"data": {"lifts": {"stats": {
    "open": 10, "hold": 1, "scheduled": 2, "closed": 3,
    "percentage": {"open": 63},
}}}}
SNOW = {
    "freshSnowfall": "5in", "topSnowDepth": "83in",
    "botSnowDepth": "40in", "lastSnowfallDate": "25 Jan 2026",
}


async def setup_area(hass: HomeAssistant, options=None, *, om=OPEN_METEO,
                     liftie=LIFTIE, skiapi=SKIAPI, snow=SNOW, area=None,
                     om_error=None, lifts_error=None,
                     wikidata=WIKIDATA, trail_map=TRAIL_MAP_URL, info_error=None):
    """Set up a ski-area entry with all api calls mocked; return (entry, mocks)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="vailid",
        title="Vail",
        data={CONF_OPENSKIMAP_ID: "vailid", CONF_NAME: "Vail",
              CONF_AREA: area or AREA},
        options={CONF_UNITS: UNIT_IMPERIAL, **(options or {})},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.ski_resort.coordinator.async_open_meteo",
               new=AsyncMock(return_value=om, side_effect=om_error)) as m_om, \
         patch("custom_components.ski_resort.coordinator.async_liftie",
               new=AsyncMock(return_value=liftie, side_effect=lifts_error)) as m_l, \
         patch("custom_components.ski_resort.coordinator.async_skiapi",
               new=AsyncMock(return_value=skiapi, side_effect=lifts_error)) as m_s, \
         patch("custom_components.ski_resort.coordinator.async_rapidapi_snow",
               new=AsyncMock(return_value=snow)) as m_snow, \
         patch("custom_components.ski_resort.coordinator.async_wikidata_item",
               new=AsyncMock(return_value=wikidata, side_effect=info_error)) as m_wd, \
         patch("custom_components.ski_resort.coordinator.async_skimap_trailmap",
               new=AsyncMock(return_value=trail_map, side_effect=info_error)) as m_tm:
        mocks = {"om": m_om, "liftie": m_l, "skiapi": m_s, "snow": m_snow,
                 "wikidata": m_wd, "trail_map": m_tm}
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, mocks
