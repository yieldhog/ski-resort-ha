"""Entity-state tests for weather, sensors, and binary sensors."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.ski_resort.const import (
    CONF_ENABLE_ALERTS,
    CONF_ENABLE_AVALANCHE,
    CONF_FORECAST_RESORT,
    CONF_LIFT_SLUG,
    CONF_RAPIDAPI_KEY,
    CONF_UNITS,
    DOMAIN,
    UNIT_METRIC,
)

from ._setup import AREA, AREA_CA, setup_area

FULL_OPTS = {CONF_LIFT_SLUG: "vail", CONF_RAPIDAPI_KEY: "k",
             CONF_FORECAST_RESORT: "Vail"}


def _state(hass, entry, key):
    registry = er.async_get(hass)
    for platform in ("sensor", "binary_sensor", "weather", "image"):
        eid = registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
        if eid:
            return hass.states.get(eid)
    return None


async def test_weather_entity(hass: HomeAssistant):
    entry, _ = await setup_area(hass)
    wx = _state(hass, entry, "weather")
    assert wx.state == "snowy"  # wmo 73
    assert wx.attributes["temperature"] == -5.0
    assert wx.attributes["apparent_temperature"] == -12.0  # feels like
    resp = await hass.services.async_call(
        "weather", "get_forecasts",
        {"entity_id": wx.entity_id, "type": "daily"},
        blocking=True, return_response=True,
    )
    forecast = resp[wx.entity_id]["forecast"]
    assert len(forecast) == 2
    assert forecast[0]["apparent_temperature"] == -9.0  # daily feels-like high


async def test_feels_like_sensor(hass: HomeAssistant):
    entry, _ = await setup_area(hass)
    assert _state(hass, entry, "feels_like").state == "-12.0"  # apparent temperature


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


async def test_precipitation_sensor(hass: HomeAssistant):
    """24h liquid precipitation: distinct from snowfall, unit-aware."""
    # Imperial: 12 mm over 24h -> 0.47 in.
    entry, _ = await setup_area(hass)
    precip = _state(hass, entry, "precipitation_24h")
    assert precip.state == "0.47"
    assert precip.attributes["unit_of_measurement"] == "in"

    # Metric: reported as mm.
    entry_m, _ = await setup_area(hass, options={CONF_UNITS: UNIT_METRIC})
    precip_m = _state(hass, entry_m, "precipitation_24h")
    assert precip_m.state == "12.0"
    assert precip_m.attributes["unit_of_measurement"] == "mm"


async def test_snow_forecast_sensor(hass: HomeAssistant):
    """5-day snow forecast: state is the total, `daily` carries each day."""
    entry, _ = await setup_area(hass)  # imperial; daily snowfall_sum [12.0, 3.0] cm
    snow = _state(hass, entry, "snow_forecast")
    assert snow.state == "5.9"  # (4.7 + 1.2) in
    daily = snow.attributes["daily"]
    assert daily == [
        # snowfall 12/3 cm -> in; precipitation 8/2 mm -> in
        {"date": "2026-01-25", "snowfall": 4.7, "precipitation": 0.31},
        {"date": "2026-01-26", "snowfall": 1.2, "precipitation": 0.08},
    ]


async def test_snow_forecast_sensor_metric(hass: HomeAssistant):
    entry, _ = await setup_area(hass, options={CONF_UNITS: UNIT_METRIC})
    snow = _state(hass, entry, "snow_forecast")
    assert snow.state == "15.0"  # 12 + 3 cm
    assert snow.attributes["daily"][0]["snowfall"] == 12.0
    assert snow.attributes["daily"][0]["precipitation"] == 8.0  # mm, metric
    assert snow.attributes["unit_of_measurement"] == "cm"


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


async def test_weather_alert_and_avalanche_when_enabled(hass: HomeAssistant):
    entry, _ = await setup_area(
        hass, options={CONF_ENABLE_ALERTS: True, CONF_ENABLE_AVALANCHE: True}
    )
    alert = _state(hass, entry, "weather_alert")
    assert alert.state == "on"
    assert alert.attributes["event"] == "Winter Storm Warning"
    assert alert.attributes["count"] == 1
    # Enriched detail is now carried on the binary sensor.
    assert alert.attributes["description"].startswith("Heavy snow")
    assert alert.attributes["instruction"].startswith("Travel could be")
    assert alert.attributes["certainty"] == "Likely"
    assert alert.attributes["sender"] == "NWS Grand Junction CO"
    # The compact list omits the verbose text to stay under the recorder limit.
    assert "description" not in alert.attributes["alerts"][0]

    # Companion text sensor: state is the human-readable event name.
    alert_status = _state(hass, entry, "active_alert")
    assert alert_status.state == "Winter Storm Warning"
    assert alert_status.attributes["headline"] == "Winter Storm Warning until 6 PM MST"
    assert alert_status.attributes["instruction"].startswith("Travel could be")

    av = _state(hass, entry, "avalanche_danger")
    assert av.state == "considerable"
    assert av.attributes["level"] == 3
    assert av.attributes["zone"] == "Vail & Summit County"
    assert av.attributes["forecast_url"].startswith("https://")


async def test_avalanche_canada(hass: HomeAssistant):
    """A Canadian resort routes to Avalanche Canada (region polygon + metadata)."""
    entry, mocks = await setup_area(
        hass, area=AREA_CA, options={CONF_ENABLE_AVALANCHE: True}
    )
    av = _state(hass, entry, "avalanche_danger")
    assert av.state == "considerable"  # highestDanger value "3"
    assert av.attributes["level"] == 3
    assert av.attributes["zone"] == "Banff Yoho Kootenay"
    assert av.attributes["center"] == "Parks Canada"
    # US avalanche.org path must not be used for a CA resort.
    mocks["avalanche"].assert_not_called()
    mocks["avalanche_ca_meta"].assert_called()


async def test_avalanche_unsupported_country_absent(hass: HomeAssistant):
    """A non-US/CA resort with the toggle on reports nothing and hits no API."""
    area_eu = {**AREA_CA, "country": "Austria", "cc": "AT"}
    entry, mocks = await setup_area(
        hass, area=area_eu, options={CONF_ENABLE_AVALANCHE: True}
    )
    assert _state(hass, entry, "avalanche_danger").state == "unavailable"
    mocks["avalanche"].assert_not_called()
    mocks["avalanche_ca_areas"].assert_not_called()


async def test_avalanche_negative_cache(hass: HomeAssistant):
    """A resort in no forecast zone latches off — no repeated global fetches."""
    from unittest.mock import AsyncMock, patch

    from ._setup import OPEN_METEO

    empty = {"type": "FeatureCollection", "features": []}
    entry, mocks = await setup_area(
        hass, options={CONF_ENABLE_AVALANCHE: True}, avalanche=empty
    )
    assert mocks["avalanche"].call_count == 1
    assert _state(hass, entry, "avalanche_danger").state == "unavailable"

    coordinator = entry.runtime_data
    with patch(
        "custom_components.ski_resort.coordinator.async_open_meteo",
        new=AsyncMock(return_value=OPEN_METEO),
    ), patch(
        "custom_components.ski_resort.coordinator.async_avalanche_map_layer",
        new=AsyncMock(return_value=empty),
    ) as m2, patch(
        "custom_components.ski_resort.coordinator.async_nws_alerts",
        new=AsyncMock(return_value=[]),
    ):
        await coordinator.async_refresh()
    assert m2.call_count == 0  # latched: no more (large) global fetches


async def test_avalanche_enum_guards_unknown_rating(hass: HomeAssistant):
    """An out-of-scale rating maps to unknown, not an invalid enum state."""
    bogus = {"type": "FeatureCollection", "features": [{
        "geometry": {"type": "Polygon", "coordinates":
                     [[[-107, 39], [-106, 39], [-106, 40], [-107, 40], [-107, 39]]]},
        "properties": {"name": "Z", "danger": "bogus", "danger_level": 9},
    }]}
    entry, _ = await setup_area(
        hass, options={CONF_ENABLE_AVALANCHE: True}, avalanche=bogus
    )
    av = _state(hass, entry, "avalanche_danger")
    assert av.state == "unknown"  # not in the enum options -> None
    assert av.attributes["level"] == 9  # attributes still populated


async def test_alerts_enabled_by_default_for_us(hass: HomeAssistant):
    """NWS alerts are on by default for a US resort (no option set)."""
    entry, mocks = await setup_area(hass)  # default options
    assert _state(hass, entry, "weather_alert").state == "on"
    assert _state(hass, entry, "active_alert").state == "Winter Storm Warning"
    mocks["alerts"].assert_called()
    # Avalanche stays opt-in (default off).
    assert _state(hass, entry, "avalanche_danger") is None


async def test_alerts_absent_when_disabled(hass: HomeAssistant):
    """Explicitly turning the alerts option off removes both entities."""
    entry, mocks = await setup_area(hass, options={CONF_ENABLE_ALERTS: False})
    assert _state(hass, entry, "weather_alert") is None
    assert _state(hass, entry, "active_alert") is None
    mocks["alerts"].assert_not_called()


async def test_alerts_absent_and_unfetched_for_non_us(hass: HomeAssistant):
    """A non-US resort never fetches or exposes alerts, even on by default."""
    entry, mocks = await setup_area(hass, area=AREA_CA)  # cc == "CA"
    assert _state(hass, entry, "weather_alert") is None
    assert _state(hass, entry, "active_alert") is None
    mocks["alerts"].assert_not_called()  # NWS has no coverage outside the US


async def test_weather_alert_off_when_none_active(hass: HomeAssistant):
    entry, _ = await setup_area(hass, options={CONF_ENABLE_ALERTS: True}, alerts=[])
    alert = _state(hass, entry, "weather_alert")
    assert alert.state == "off"  # queried OK, just nothing active
    assert alert.attributes["count"] == 0
    # The text sensor reads "None" when clear (not "unknown"/"unavailable").
    status = _state(hass, entry, "active_alert")
    assert status.state == "None"
    assert status.attributes["count"] == 0


async def test_resort_info_sensor(hass: HomeAssistant):
    entry, _ = await setup_area(hass)
    info = _state(hass, entry, "resort_info")
    assert info.state == "operating"
    assert info.attributes["region"] == "Colorado"
    assert info.attributes["website"] == "https://www.vail.com"
    assert info.attributes["openskimap_url"].endswith("vailid")
    assert info.attributes["wikidata_url"].endswith("Q14685139")
    assert info.attributes["skimap_url"].endswith("507")
    assert info.attributes["opening_year"] == 1962  # from Wikidata P571


async def test_image_entities(hass: HomeAssistant):
    entry, mocks = await setup_area(hass)
    # The Wikidata photo entity was removed; only the trail map remains.
    assert _state(hass, entry, "photo") is None
    trail = _state(hass, entry, "trail_map")
    assert trail is not None and trail.attributes.get("entity_picture")
    # Wikidata is still fetched once (for website + opening year on the info sensor).
    mocks["wikidata"].assert_called_once()
    mocks["trail_map"].assert_called_once()


async def test_no_enrichment_without_ids(hass: HomeAssistant):
    """An area with no Wikidata/skimap ids has no image entities."""
    bare = dict(AREA)
    bare.pop("wd")
    bare.pop("sk")
    entry, _ = await setup_area(hass, area=bare)
    assert _state(hass, entry, "photo") is None
    assert _state(hass, entry, "trail_map") is None
    # Info sensor is still present, without the enrichment links.
    info = _state(hass, entry, "resort_info")
    assert "wikidata_url" not in info.attributes
