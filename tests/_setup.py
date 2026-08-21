"""Shared setup helper for entry/coordinator tests (not collected as tests)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ski_resort.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_RESORT,
    CONF_UNITS,
    DOMAIN,
    UNIT_IMPERIAL,
)

SNOW = {
    "freshSnowfall": "5in",
    "topSnowDepth": "83in",
    "botSnowDepth": "40in",
    "lastSnowfallDate": "25 Jan 2026",
}
FORECAST = {
    "summary3Day": "Snow expected",
    "summary5Day": "More snow later in the week",
    "forecast5Day": [{"day": "Mon", "snow": "5in"}, {"day": "Tue", "snow": "2in"}],
    "basicInfo": {
        "name": "Vail",
        "region": "Colorado",
        "url": "https://example.com/vail",
    },
}
LIFTS = {
    "data": {
        "name": "Vail",
        "lifts": {
            "status": {"lift-1": "open"},
            "stats": {
                "open": 10,
                "hold": 1,
                "scheduled": 2,
                "closed": 3,
                "percentage": {"open": 63, "hold": 6, "scheduled": 12, "closed": 19},
            },
        },
    }
}


def make_client(snow=SNOW, forecast=FORECAST, lifts=LIFTS, **side_effects):
    """Build an AsyncMock SkiResortClient with the given payloads.

    Pass ``snow_side_effect`` / ``forecast_side_effect`` / ``lifts_side_effect``
    to raise instead of returning.
    """
    client = AsyncMock()
    client.async_get_snow_conditions = AsyncMock(
        return_value=snow, side_effect=side_effects.get("snow_side_effect")
    )
    client.async_get_forecast = AsyncMock(
        return_value=forecast, side_effect=side_effects.get("forecast_side_effect")
    )
    client.async_get_lift_status = AsyncMock(
        return_value=lifts, side_effect=side_effects.get("lifts_side_effect")
    )
    return client


async def setup_resort(hass: HomeAssistant, options=None, client=None):
    """Add and set up a resort entry with a mocked client; return (entry, client)."""
    client = client or make_client()
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="vail",
        title="Vail Mountain",
        data={CONF_API_KEY: "key", CONF_RESORT: "Vail", CONF_NAME: "Vail Mountain"},
        options={CONF_UNITS: UNIT_IMPERIAL, **(options or {})},
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.ski_resort.SkiResortClient", return_value=client
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, client
