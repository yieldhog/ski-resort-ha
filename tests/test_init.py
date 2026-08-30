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


async def test_info_failure_is_non_fatal(hass: HomeAssistant):
    """Enrichment failing (Wikidata/skimap) does not break setup."""
    from custom_components.ski_resort.const import DATA_INFO

    entry, _ = await setup_area(hass, info_error=SkiResortConnectionError("down"))
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.data[DATA_INFO] == {}


async def test_info_retries_after_transient_failure(hass: HomeAssistant):
    """A transient enrichment failure isn't latched: the next poll repopulates."""
    from unittest.mock import AsyncMock, patch

    from custom_components.ski_resort.const import DATA_INFO

    from ._setup import LIFTIE, OPEN_METEO, TRAIL_MAP_URL, WIKIDATA

    # First refresh fails enrichment -> empty for this cycle, but not cached.
    entry, _ = await setup_area(hass, info_error=SkiResortConnectionError("down"))
    coordinator = entry.runtime_data
    assert coordinator.data[DATA_INFO] == {}

    # Next poll: enrichment now succeeds and is picked up (proving no latch).
    with patch(
        "custom_components.ski_resort.coordinator.async_open_meteo",
        new=AsyncMock(return_value=OPEN_METEO),
    ), patch(
        "custom_components.ski_resort.coordinator.async_liftie",
        new=AsyncMock(return_value=LIFTIE),
    ), patch(
        "custom_components.ski_resort.coordinator.async_wikidata_item",
        new=AsyncMock(return_value=WIKIDATA),
    ), patch(
        "custom_components.ski_resort.coordinator.async_skimap_trailmap",
        new=AsyncMock(return_value=TRAIL_MAP_URL),
    ), patch(
        # Alerts are on by default for this US resort; stub the fetch so the
        # refresh doesn't reach the (blocked) network.
        "custom_components.ski_resort.coordinator.async_nws_alerts",
        new=AsyncMock(return_value=[]),
    ):
        await coordinator.async_refresh()

    assert coordinator.data[DATA_INFO].get("trail_map_url") == TRAIL_MAP_URL


async def test_rapidapi_snow_is_throttled(hass: HomeAssistant):
    """The metered RapidAPI snow source is fetched at most once per interval."""
    from unittest.mock import AsyncMock, patch

    from custom_components.ski_resort.const import (
        CONF_FORECAST_RESORT,
        CONF_RAPIDAPI_KEY,
        DATA_SNOW,
    )

    from ._setup import LIFTIE, OPEN_METEO, SNOW

    opts = {CONF_RAPIDAPI_KEY: "k", CONF_FORECAST_RESORT: "Vail"}
    entry, mocks = await setup_area(hass, options=opts)
    assert mocks["snow"].call_count == 1  # fetched once at first refresh
    coordinator = entry.runtime_data
    snow_before = coordinator.data[DATA_SNOW]
    assert snow_before is not None

    # A poll within the interval must not re-hit RapidAPI, but keeps last-good.
    with patch(
        "custom_components.ski_resort.coordinator.async_open_meteo",
        new=AsyncMock(return_value=OPEN_METEO),
    ), patch(
        "custom_components.ski_resort.coordinator.async_liftie",
        new=AsyncMock(return_value=LIFTIE),
    ), patch(
        "custom_components.ski_resort.coordinator.async_rapidapi_snow",
        new=AsyncMock(return_value=SNOW),
    ) as m_snow2, patch(
        "custom_components.ski_resort.coordinator.async_nws_alerts",
        new=AsyncMock(return_value=[]),
    ):
        await coordinator.async_refresh()

    assert m_snow2.call_count == 0  # throttled
    assert coordinator.data[DATA_SNOW] == snow_before  # last-good retained


async def test_auth_error_on_optional_source_degrades(hass: HomeAssistant):
    """A bad RapidAPI key (auth error) disables lifts, not the whole entry."""
    from custom_components.ski_resort.api import SkiResortAuthError

    entry, _ = await setup_area(
        hass,
        options={CONF_LIFT_SLUG: "vail", CONF_RAPIDAPI_KEY: "bad"},
        lifts_error=SkiResortAuthError("key rejected"),
    )
    assert entry.state is ConfigEntryState.LOADED  # weather still works
    assert entry.runtime_data.data[DATA_LIFTS] is None


async def test_lift_slug_without_source_yields_no_lifts(hass: HomeAssistant):
    """A slug with no Liftie URL and no key produces no lift data."""
    entry, _ = await setup_area(hass, options={CONF_LIFT_SLUG: "vail"})
    assert entry.runtime_data.data[DATA_LIFTS] is None


async def test_missing_area_data_errors(hass: HomeAssistant):
    """An entry lacking the OpenSkiMap area snapshot fails setup with a message."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.ski_resort.const import DOMAIN

    entry = MockConfigEntry(domain=DOMAIN, unique_id="oldid",
                            data={"id": "oldid", "name": "Legacy"})  # no CONF_AREA
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
