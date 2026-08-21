"""Setup, coordinator shaping, trend, and resilience tests."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.ski_resort.api import (
    SkiResortApiError,
    SkiResortAuthError,
    SkiResortConnectionError,
)
from custom_components.ski_resort.const import (
    CONF_ENABLE_LIFTS,
    CONF_LIFT_SLUG,
    DATA_LIFTS,
    DATA_SNOW,
    SNOW_TOP,
    SNOW_TOP_CHANGE,
    SNOW_TOP_TREND,
)

from ._setup import make_client, setup_resort


async def test_setup_shapes_snow(hass: HomeAssistant):
    """A successful refresh normalizes the snow bundle."""
    entry, _ = await setup_resort(hass)
    assert entry.state is ConfigEntryState.LOADED
    snow = entry.runtime_data.data[DATA_SNOW]
    assert snow["fresh"] == 5.0
    assert snow[SNOW_TOP] == 83.0
    assert snow["base_depth"] == 40.0
    assert snow["last_snow_date"].isoformat() == "2026-01-25"
    # First poll: no prior reading, so no trend yet.
    assert snow[SNOW_TOP_TREND] is None
    assert snow[SNOW_TOP_CHANGE] is None


async def test_trend_computed_on_second_refresh(hass: HomeAssistant):
    """Top-depth trend/change are tagged against the previous poll."""
    client = make_client()
    entry, _ = await setup_resort(hass, client=client)
    client.async_get_snow_conditions.return_value = {
        "topSnowDepth": "90in",
        "freshSnowfall": "7in",
        "botSnowDepth": "44in",
    }
    await entry.runtime_data.async_refresh()
    snow = entry.runtime_data.data[DATA_SNOW]
    assert snow[SNOW_TOP] == 90.0
    assert snow[SNOW_TOP_TREND] == "up"
    assert snow[SNOW_TOP_CHANGE] == 7.0


async def test_fresh_snow_null_floors_to_zero(hass: HomeAssistant):
    """A null freshSnowfall means none fell → 0.0, not unavailable."""
    client = make_client(snow={"topSnowDepth": "80in", "freshSnowfall": None})
    entry, _ = await setup_resort(hass, client=client)
    assert entry.runtime_data.data[DATA_SNOW]["fresh"] == 0.0


async def test_lifts_disabled_by_default(hass: HomeAssistant):
    """Without the toggle, lift status is not fetched or shaped."""
    entry, client = await setup_resort(hass)
    client.async_get_lift_status.assert_not_called()
    assert entry.runtime_data.data[DATA_LIFTS] is None


async def test_lifts_enabled_shapes_stats(hass: HomeAssistant):
    """Enabling lifts (with a slug) fetches and flattens the stats."""
    entry, client = await setup_resort(
        hass, options={CONF_ENABLE_LIFTS: True, CONF_LIFT_SLUG: "vail"}
    )
    client.async_get_lift_status.assert_called_once()
    lifts = entry.runtime_data.data[DATA_LIFTS]
    assert lifts["open"] == 10
    assert lifts["total"] == 16
    assert lifts["percentage"]["open"] == 63


async def test_section_degrades_without_blanking_resort(hass: HomeAssistant):
    """One failing section (snow) degrades but the forecast still publishes."""
    client = make_client(
        snow_side_effect=SkiResortConnectionError("snow down")
    )
    entry, _ = await setup_resort(hass, client=client)
    assert entry.state is ConfigEntryState.LOADED
    data = entry.runtime_data.data
    assert data[DATA_SNOW][SNOW_TOP] is None  # snow missing
    assert data["forecast"]["summary3Day"] == "Snow expected"  # forecast survived


async def test_total_failure_sets_retry(hass: HomeAssistant):
    """If every section fails, setup goes to retry (entities unavailable)."""
    client = make_client(
        snow_side_effect=SkiResortApiError("x", 500),
        forecast_side_effect=SkiResortApiError("y", 500),
    )
    entry, _ = await setup_resort(hass, client=client)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_auth_failure_triggers_reauth(hass: HomeAssistant):
    """An auth error propagates as ConfigEntryAuthFailed → reauth flow."""
    client = make_client(snow_side_effect=SkiResortAuthError("bad key"))
    entry, _ = await setup_resort(hass, client=client)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"].get("source") == "reauth" for f in flows)


async def test_unload(hass: HomeAssistant):
    """The entry unloads cleanly."""
    entry, _ = await setup_resort(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
