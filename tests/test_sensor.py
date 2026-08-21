"""Entity-state tests for sensors and binary sensors."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.ski_resort.const import (
    CONF_ENABLE_LIFTS,
    CONF_LIFT_SLUG,
    DOMAIN,
)

from ._setup import make_client, setup_resort


def _state(hass, entry, key):
    """Resolve an entity by its unique-id suffix and return its state object."""
    registry = er.async_get(hass)
    for platform in ("sensor", "binary_sensor"):
        entity_id = registry.async_get_entity_id(
            platform, DOMAIN, f"{entry.entry_id}_{key}"
        )
        if entity_id:
            return hass.states.get(entity_id)
    return None


async def test_snow_sensor_states(hass: HomeAssistant):
    """Snow sensors carry parsed values and the right units."""
    entry, _ = await setup_resort(hass)
    fresh = _state(hass, entry, "fresh_snow")
    assert fresh.state == "5.0"
    assert fresh.attributes["unit_of_measurement"] == "in"

    top = _state(hass, entry, "top_snow_depth")
    assert top.state == "83.0"
    assert top.attributes["trend"] is None  # first poll

    assert _state(hass, entry, "last_snow_date").state == "2026-01-25"


async def test_forecast_sensor_attributes(hass: HomeAssistant):
    """The forecast sensor exposes the 5-day payload and resort info."""
    entry, _ = await setup_resort(hass)
    fc = _state(hass, entry, "forecast_3day")
    assert fc.state == "Snow expected"
    assert fc.attributes["summary_5day"] == "More snow later in the week"
    assert len(fc.attributes["forecast_5day"]) == 2
    assert fc.attributes["resort_info"]["region"] == "Colorado"


async def test_forecast_summary_truncated(hass: HomeAssistant):
    """An over-long summary is truncated in state but kept whole in attrs."""
    long_summary = "x" * 400
    client = make_client(
        forecast={"summary3Day": long_summary, "basicInfo": {}}
    )
    entry, _ = await setup_resort(hass, client=client)
    fc = _state(hass, entry, "forecast_3day")
    assert len(fc.state) == 255
    assert fc.attributes["summary_3day"] == long_summary


async def test_powder_day_on(hass: HomeAssistant):
    """Powder-day binary sensor is on when fresh snow > 0."""
    entry, _ = await setup_resort(hass)
    assert _state(hass, entry, "powder_day").state == "on"


async def test_powder_day_off_without_fresh_snow(hass: HomeAssistant):
    """No fresh snow → powder-day is off."""
    client = make_client(snow={"topSnowDepth": "80in", "freshSnowfall": "0in"})
    entry, _ = await setup_resort(hass, client=client)
    assert _state(hass, entry, "powder_day").state == "off"


async def test_lift_sensors_present_when_enabled(hass: HomeAssistant):
    """Lift sensors + resort-open appear and read the flattened stats."""
    entry, _ = await setup_resort(
        hass, options={CONF_ENABLE_LIFTS: True, CONF_LIFT_SLUG: "vail"}
    )
    assert _state(hass, entry, "lifts_open").state == "10"
    assert _state(hass, entry, "lifts_total").state == "16"
    assert _state(hass, entry, "lifts_open_percent").state == "63"
    open_attrs = _state(hass, entry, "lifts_open").attributes
    assert open_attrs["closed"] == 3
    assert _state(hass, entry, "resort_open").state == "on"


async def test_lift_sensors_absent_when_disabled(hass: HomeAssistant):
    """No lift entities are created when the toggle is off."""
    entry, _ = await setup_resort(hass)
    assert _state(hass, entry, "lifts_open") is None
    assert _state(hass, entry, "resort_open") is None


async def test_lift_sensors_unavailable_on_bad_slug(hass: HomeAssistant):
    """Enabled but an unusable lift payload → lift sensors are unavailable."""
    client = make_client(lifts={"unexpected": True})
    entry, _ = await setup_resort(
        hass,
        options={CONF_ENABLE_LIFTS: True, CONF_LIFT_SLUG: "wrong"},
        client=client,
    )
    assert _state(hass, entry, "lifts_open").state == "unavailable"


async def test_forecast_no_summary_is_unknown(hass: HomeAssistant):
    """A forecast without a summary string leaves the sensor unknown."""
    client = make_client(forecast={"basicInfo": {}})
    entry, _ = await setup_resort(hass, client=client)
    assert _state(hass, entry, "forecast_3day").state == "unknown"


async def test_lifts_percent_unavailable_without_percentage(hass: HomeAssistant):
    """A stats block lacking a percentage dict leaves the percent sensor off."""
    client = make_client(
        lifts={"data": {"lifts": {"stats": {"open": 4, "closed": 1}}}}
    )
    entry, _ = await setup_resort(
        hass,
        options={"lifts_enabled": True, "lift_slug": "vail"},
        client=client,
    )
    assert _state(hass, entry, "lifts_open").state == "4"
    assert _state(hass, entry, "lifts_open_percent").state == "unavailable"
