"""Diagnostics for the Ski Resort integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SkiResortConfigEntry
from .const import CONF_LIFTIE_BASE_URL, CONF_RAPIDAPI_KEY

# The RapidAPI key is secret; a self-hosted Liftie URL may reveal an internal host.
TO_REDACT = {CONF_RAPIDAPI_KEY, CONF_LIFTIE_BASE_URL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SkiResortConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "data": dict(entry.data),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "data": coordinator.data,
    }
