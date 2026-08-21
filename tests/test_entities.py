"""Entity-state tests for weather, sensors, and binary sensors."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.ski_resort.const import (
    CONF_FORECAST_RESORT,
    CONF_LIFT_SLUG,
    CONF_RAPIDAPI_KEY,
    CONF_UNITS,
    DOMAIN,
    UNIT_METRIC,
)

from ._setup import setup_area

FULL_OPTS = {CONF_LIFT_SLUG: "vail", CONF_RAPIDAPI_KEY: "k",
             CONF_FORECAST_RESORT: "Vail"}


def _state(hass, entry, key):
    registry = er.async_get(hass)
    for platform in ("sensor", "binary_sensor", "weather"):
        eid = registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
        if eid:
            return hass.states.get(eid)
    return None


async def test_weather_entity(hass: HomeAssistant):
    entry, _ = await setup_area(hass)
    wx = _state(hass, entry, "weather")
    assert wx.state == "snowy"  # wmo 73
    assert wx.attributes["temperature"] == -5.0
    resp = await hass.services.async_call(
        "weather", "get_forecasts",
        {"entity_id": wx.entity_id, "type": "daily"},
        blocking=True, return_response=True,
    )
    assert len(resp[wx.entity_id]["forecast"]) == 2


async def test_snow_and_terrain_sensors_imperial(hass: HomeAssistant):
    entry, _ = await setup_area(hass)  # default imperial
    assert _state(hass, entry, "fresh_snow").state == "9.4"  # 24cm -> in
    assert _state(hass, entry, "snow_depth").state == "47.2"  # 1.2m -> in
    assert _state(hass, entry, "freezing_level").state == "8202"  # 2500m -> ft
    assert _state(hass, entry, "lift_count").state == "32"
    assert _state(hass, entry, "run_count").state == "241"
    assert _state(hass, entry, "run_count").attributes["by_difficulty"]["advanced"] == 110
    assert _state(hass, entry, "vertical_drop").state == "3494"  # 1065m -> ft
    assert _state(hass, entry, "summit_elevation").state == "11538"
    assert _state(hass, entry, "base_elevation").state == "8044"


async def test_metric_units(hass: HomeAssistant):
    entry, _ = await setup_area(hass, options={CONF_UNITS: UNIT_METRIC})
    fresh = _state(hass, entry, "fresh_snow")
    assert fresh.state == "24.0"
    assert fresh.attributes["unit_of_measurement"] == "cm"


async def test_lift_and_reported_sensors(hass: HomeAssistant):
    entry, _ = await setup_area(hass, options=FULL_OPTS)
    assert _state(hass, entry, "lifts_open").state == "10"
    assert _state(hass, entry, "lifts_open").attributes["source"] == "skiapi"
    assert _state(hass, entry, "lifts_open_percent").state == "31"
    assert _state(hass, entry, "resort_open").state == "on"
    assert _state(hass, entry, "reported_summit_depth").state == "83.0"
    assert _state(hass, entry, "reported_base_depth").state == "40.0"
    assert _state(hass, entry, "reported_fresh_snow").state == "5.0"
    assert _state(hass, entry, "last_snow_date").state == "2026-01-25"


async def test_powder_day_on(hass: HomeAssistant):
    entry, _ = await setup_area(hass)  # 24cm forecast >= 10 threshold
    assert _state(hass, entry, "powder_day").state == "on"


async def test_lift_sensors_absent_without_source(hass: HomeAssistant):
    entry, _ = await setup_area(hass)  # no lift options
    assert _state(hass, entry, "lifts_open") is None
    assert _state(hass, entry, "resort_open") is None
