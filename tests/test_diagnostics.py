"""Diagnostics redaction test."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.ski_resort.diagnostics import (
    async_get_config_entry_diagnostics,
)

from ._setup import setup_resort


async def test_diagnostics_redacts_key(hass: HomeAssistant):
    """The API key is redacted; shaped data is included."""
    entry, _ = await setup_resort(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"]["data"]["api_key"] == "**REDACTED**"
    assert diag["entry"]["data"]["resort"] == "Vail"
    assert "snow" in diag["data"]
