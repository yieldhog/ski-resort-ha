"""Diagnostics redaction test."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.ski_resort.const import (
    CONF_LIFT_SLUG,
    CONF_LIFTIE_BASE_URL,
    CONF_RAPIDAPI_KEY,
)
from custom_components.ski_resort.diagnostics import (
    async_get_config_entry_diagnostics,
)

from ._setup import setup_area


async def test_diagnostics_redacts_secrets(hass: HomeAssistant):
    entry, _ = await setup_area(
        hass,
        options={CONF_LIFT_SLUG: "vail", CONF_RAPIDAPI_KEY: "secret",
                 CONF_LIFTIE_BASE_URL: "http://internal:3000"},
    )
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"]["options"][CONF_RAPIDAPI_KEY] == "**REDACTED**"
    assert diag["entry"]["options"][CONF_LIFTIE_BASE_URL] == "**REDACTED**"
    assert diag["entry"]["data"]["id"] == "vailid"
