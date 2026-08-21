"""Setup, coordinator shaping, and resilience tests."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.ski_resort.api import SkiResortConnectionError
from custom_components.ski_resort.const import (
    CONF_LIFT_SLUG,
    CONF_LIFTIE_BASE_URL,
    CONF_RAPIDAPI_KEY,
    DATA_LIFTS,
    DATA_WEATHER,
    WX_FRESH_SNOW,
    WX_SNOW_DEPTH,
)

from ._setup import setup_area


async def test_setup_weather(hass: HomeAssistant):
    """Open-Meteo shapes into fresh-snow (24h) and depth; no lifts by default."""
    entry, mocks = await setup_area(hass)
    assert entry.state is ConfigEntryState.LOADED
    weather = entry.runtime_data.data[DATA_WEATHER]
    assert weather[WX_FRESH_SNOW] == 24.0  # 24 * 1.0 cm
    assert weather[WX_SNOW_DEPTH] == 1.2  # metres
    assert entry.runtime_data.data[DATA_LIFTS] is None
    mocks["liftie"].assert_not_called()


async def test_lifts_via_liftie(hass: HomeAssistant):
    """A Liftie base URL routes lifts through Liftie; total from OpenSkiMap."""
    entry, mocks = await setup_area(
        hass, options={CONF_LIFT_SLUG: "vail",
                       CONF_LIFTIE_BASE_URL: "http://liftie.local"}
    )
    lifts = entry.runtime_data.data[DATA_LIFTS]
    assert lifts["open"] == 10
    assert lifts["total"] == 32  # OpenSkiMap authoritative
    assert lifts["percentage"] == 31  # round(10/32*100)
    assert lifts["source"] == "liftie"
    mocks["liftie"].assert_called_once()
    mocks["skiapi"].assert_not_called()


async def test_lifts_via_skiapi(hass: HomeAssistant):
    """A RapidAPI key (no Liftie URL) routes lifts through skiapi."""
    entry, mocks = await setup_area(
        hass, options={CONF_LIFT_SLUG: "vail", CONF_RAPIDAPI_KEY: "k"}
    )
    lifts = entry.runtime_data.data[DATA_LIFTS]
    assert lifts["source"] == "skiapi"
    assert lifts["open"] == 10
    mocks["skiapi"].assert_called_once()


async def test_weather_degrades_but_lifts_survive(hass: HomeAssistant):
    """Open-Meteo failing degrades weather but keeps the entry loaded via lifts."""
    entry, _ = await setup_area(
        hass,
        options={CONF_LIFT_SLUG: "vail", CONF_LIFTIE_BASE_URL: "http://l"},
        om_error=SkiResortConnectionError("down"),
    )
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.data[DATA_WEATHER] is None
    assert entry.runtime_data.data[DATA_LIFTS] is not None


async def test_total_failure_retries(hass: HomeAssistant):
    """If weather fails and there's no other source, setup retries."""
    entry, _ = await setup_area(hass, om_error=SkiResortConnectionError("down"))
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload(hass: HomeAssistant):
    entry, _ = await setup_area(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
