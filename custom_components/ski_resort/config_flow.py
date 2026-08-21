"""Config and options flow for the Ski Resort Forecast integration.

User flow: RapidAPI key + resort name (+ units), validated by a live snow-
conditions fetch. One config entry == one resort; add more resorts by running
the flow again. A reauth step re-collects the key when it stops working.

Options: poll interval, units, forecast elevation, and an opt-in lift-status
toggle (with the skiapi slug) that gates the second product's fetch.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .api import (
    SkiResortApiError,
    SkiResortAuthError,
    SkiResortClient,
    SkiResortConnectionError,
)
from .const import (
    CONF_API_KEY,
    CONF_ELEVATION,
    CONF_ENABLE_LIFTS,
    CONF_LIFT_SLUG,
    CONF_NAME,
    CONF_RESORT,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_UNITS,
    DEFAULT_ELEVATION,
    DEFAULT_ENABLE_LIFTS,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_UNITS,
    DOMAIN,
    ELEVATIONS,
    MIN_SCAN_INTERVAL_MINUTES,
    UNIT_QUERY,
    UNITS,
)
from .helpers import slugify_resort


async def _validate(
    hass: Any, api_key: str, resort: str, units: str
) -> None:
    """Validate the key + resort by fetching snow conditions.

    Raises the client's typed errors so the caller can map them to form errors.
    """
    client = SkiResortClient(hass, api_key)
    await client.async_validate_resort(resort, UNIT_QUERY.get(units, "i"))


class SkiResortConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup and reauth for a resort."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the key, resort, name, and units for a new resort."""
        errors: dict[str, str] = {}
        if user_input is not None:
            resort = user_input[CONF_RESORT].strip()
            units = user_input[CONF_UNITS]
            await self.async_set_unique_id(slugify_resort(resort))
            self._abort_if_unique_id_configured()
            try:
                await _validate(
                    self.hass, user_input[CONF_API_KEY], resort, units
                )
            except SkiResortAuthError:
                errors["base"] = "invalid_auth"
            except SkiResortApiError:
                errors["base"] = "unknown_resort"
            except SkiResortConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or resort,
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_RESORT: resort,
                        CONF_NAME: user_input.get(CONF_NAME) or resort,
                    },
                    options={CONF_UNITS: units},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_RESORT): str,
                    vol.Optional(CONF_NAME): str,
                    vol.Required(CONF_UNITS, default=DEFAULT_UNITS): vol.In(UNITS),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth when the stored key stops working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect a fresh RapidAPI key and validate it against this resort."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            units = entry.options.get(CONF_UNITS, DEFAULT_UNITS)
            try:
                await _validate(
                    self.hass,
                    user_input[CONF_API_KEY],
                    entry.data[CONF_RESORT],
                    units,
                )
            except SkiResortAuthError:
                errors["base"] = "invalid_auth"
            except SkiResortApiError:
                errors["base"] = "unknown_resort"
            except SkiResortConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
            description_placeholders={"resort": entry.data[CONF_RESORT]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> SkiResortOptionsFlow:
        """Return the options flow handler."""
        return SkiResortOptionsFlow()


class SkiResortOptionsFlow(OptionsFlow):
    """Handle interval, units, elevation, and the lift-status toggle."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and persist the options form."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        opts = self.config_entry.options
        default_slug = opts.get(CONF_LIFT_SLUG) or slugify_resort(
            self.config_entry.data[CONF_RESORT]
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL_MINUTES,
                    default=opts.get(
                        CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
                    ),
                ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL_MINUTES)),
                vol.Required(
                    CONF_UNITS, default=opts.get(CONF_UNITS, DEFAULT_UNITS)
                ): vol.In(UNITS),
                vol.Required(
                    CONF_ELEVATION,
                    default=opts.get(CONF_ELEVATION, DEFAULT_ELEVATION),
                ): vol.In(ELEVATIONS),
                vol.Required(
                    CONF_ENABLE_LIFTS,
                    default=opts.get(CONF_ENABLE_LIFTS, DEFAULT_ENABLE_LIFTS),
                ): bool,
                vol.Optional(CONF_LIFT_SLUG, default=default_slug): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
