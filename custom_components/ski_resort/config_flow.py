"""Config and options flow for the Ski Resort integration.

Setup searches the bundled OpenSkiMap index — no API key required (weather comes
from free Open-Meteo). Steps:

1. ``user``   — a name query + optional country filter.
2. ``select`` — pick the matching ski area (and an optional display name).

One config entry == one ski area, keyed by its OpenSkiMap id. Options add units,
poll interval, an optional RapidAPI key (RapidAPI snow + skiapi lifts), a
self-hosted Liftie URL, and the lift slug (auto-filled from the crosswalk).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import data as ski_data
from .const import (
    CONF_AREA,
    CONF_COUNTRY,
    CONF_ENABLE_ALERTS,
    CONF_ENABLE_AVALANCHE,
    CONF_FORECAST_INTERVAL_HOURS,
    CONF_FORECAST_RESORT,
    CONF_LIFT_SLUG,
    CONF_LIFTIE_BASE_URL,
    CONF_NAME,
    CONF_OPENSKIMAP_ID,
    CONF_QUERY,
    CONF_RAPIDAPI_KEY,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_SKI_AREA,
    CONF_UNITS,
    CONF_WEBCAM_URL,
    DEFAULT_FORECAST_INTERVAL_HOURS,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_UNITS,
    DOMAIN,
    MIN_FORECAST_INTERVAL_HOURS,
    MIN_SCAN_INTERVAL_MINUTES,
    UNITS,
)


def _area_label(area: dict[str, Any]) -> str:
    parts = [area.get("name") or "Unknown"]
    where = ", ".join(p for p in (area.get("region"), area.get("country")) if p)
    if where:
        parts.append(f"— {where}")
    if area.get("lifts"):
        parts.append(f"· {area['lifts']} lifts")
    return " ".join(parts)


class SkiResortConfigFlow(ConfigFlow, domain=DOMAIN):
    """Search OpenSkiMap and add a ski area."""

    VERSION = 1

    def __init__(self) -> None:
        """Hold state across the query/select steps."""
        self._matches: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect a name query + optional country, then search the index."""
        errors: dict[str, str] = {}
        countries = await self.hass.async_add_executor_job(ski_data.countries)
        if user_input is not None:
            query = user_input[CONF_QUERY].strip()
            country = user_input.get(CONF_COUNTRY) or None
            self._matches = await self.hass.async_add_executor_job(
                ski_data.search_areas, query, country
            )
            if not self._matches:
                errors["base"] = "no_results"
            else:
                return await self.async_step_select()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_QUERY): str,
                    vol.Optional(CONF_COUNTRY): SelectSelector(
                        SelectSelectorConfig(
                            options=countries,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=False,
                            sort=True,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the matching ski area and create the entry."""
        if user_input is not None:
            area_id = user_input[CONF_SKI_AREA]
            area = await self.hass.async_add_executor_job(ski_data.get_area, area_id)
            if area is None:
                # The bundled index changed under an open flow; start over.
                return self.async_abort(reason="area_not_found")
            await self.async_set_unique_id(area_id)
            self._abort_if_unique_id_configured()
            name = str(
                (user_input.get(CONF_NAME) or "").strip()
                or area.get("name")
                or area_id
            )
            slug = await self.hass.async_add_executor_job(
                ski_data.liftie_slug_for, area_id
            )
            return self.async_create_entry(
                title=name,
                data={
                    CONF_OPENSKIMAP_ID: area_id,
                    CONF_NAME: name,
                    CONF_AREA: area,
                },
                options={
                    CONF_UNITS: DEFAULT_UNITS,
                    CONF_LIFT_SLUG: slug or "",
                },
            )

        options = [
            SelectOptionDict(value=area["id"], label=_area_label(area))
            for area in self._matches
        ]
        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SKI_AREA): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.LIST
                        )
                    ),
                    vol.Optional(CONF_NAME): str,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> SkiResortOptionsFlow:
        """Return the options flow handler."""
        return SkiResortOptionsFlow()


class SkiResortOptionsFlow(OptionsFlow):
    """Units, interval, and optional provider settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and persist the options form."""
        errors: dict[str, str] = {}
        if user_input is not None:
            for field in (CONF_LIFTIE_BASE_URL, CONF_WEBCAM_URL):
                value = (user_input.get(field) or "").strip()
                if value and not value.startswith(("http://", "https://")):
                    errors[field] = "invalid_url"
            if not errors:
                # Drop blank optional strings so unset stays unset.
                cleaned = {
                    k: v
                    for k, v in user_input.items()
                    if not (isinstance(v, str) and not v)
                }
                return self.async_create_entry(data=cleaned)

        opts = self.config_entry.options

        def optional(key: str) -> vol.Optional:
            """An optional text field pre-filled from the current value.

            Uses ``suggested_value`` (not ``default``) so a cleared field stays
            cleared: the HA frontend omits an emptied optional field, and a
            ``default`` would silently re-inject the old value — meaning e.g.
            blanking the webcam URL would never actually remove it.
            """
            return vol.Optional(
                key, description={"suggested_value": opts.get(key) or None}
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
                    CONF_ENABLE_ALERTS,
                    default=opts.get(CONF_ENABLE_ALERTS, False),
                ): bool,
                vol.Required(
                    CONF_ENABLE_AVALANCHE,
                    default=opts.get(CONF_ENABLE_AVALANCHE, False),
                ): bool,
                optional(CONF_LIFT_SLUG): str,
                optional(CONF_LIFTIE_BASE_URL): str,
                optional(CONF_RAPIDAPI_KEY): str,
                optional(CONF_FORECAST_RESORT): str,
                vol.Required(
                    CONF_FORECAST_INTERVAL_HOURS,
                    default=opts.get(
                        CONF_FORECAST_INTERVAL_HOURS, DEFAULT_FORECAST_INTERVAL_HOURS
                    ),
                ): vol.All(int, vol.Range(min=MIN_FORECAST_INTERVAL_HOURS)),
                optional(CONF_WEBCAM_URL): str,
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
