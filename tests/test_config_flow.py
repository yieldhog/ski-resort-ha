"""Tests for the Ski Resort Forecast config and options flows.

Held to 100% coverage in CI: every user/reauth error branch and both option
default-slug branches are exercised.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ski_resort.api import (
    SkiResortApiError,
    SkiResortAuthError,
    SkiResortConnectionError,
)
from custom_components.ski_resort.const import (
    CONF_API_KEY,
    CONF_ELEVATION,
    CONF_ENABLE_LIFTS,
    CONF_LIFT_SLUG,
    CONF_NAME,
    CONF_RESORT,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_UNITS,
    DOMAIN,
    UNIT_IMPERIAL,
)

USER_INPUT = {
    CONF_API_KEY: "key",
    CONF_RESORT: "Vail",
    CONF_NAME: "Vail Mountain",
    CONF_UNITS: UNIT_IMPERIAL,
}


def _patch_client(side_effect=None):
    """Patch the config-flow client with a fake whose validate is wired.

    Returns the patch context manager; use it in a ``with`` block.
    """
    fake = AsyncMock()
    fake.async_validate_resort = AsyncMock(return_value={}, side_effect=side_effect)
    return patch(
        "custom_components.ski_resort.config_flow.SkiResortClient", return_value=fake
    )


async def test_user_flow_success(hass: HomeAssistant):
    """Happy path: key + resort validates and creates an entry."""
    with _patch_client(), patch(
        "custom_components.ski_resort.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vail Mountain"
    assert result["data"][CONF_RESORT] == "Vail"
    assert result["data"][CONF_NAME] == "Vail Mountain"
    assert result["options"] == {CONF_UNITS: UNIT_IMPERIAL}


async def test_user_flow_default_name_is_resort(hass: HomeAssistant):
    """Omitting the display name falls back to the resort name."""
    payload = {CONF_API_KEY: "key", CONF_RESORT: "Aspen", CONF_UNITS: UNIT_IMPERIAL}
    with _patch_client(), patch(
        "custom_components.ski_resort.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], payload
        )
    assert result["title"] == "Aspen"
    assert result["data"][CONF_NAME] == "Aspen"


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (SkiResortAuthError("bad key"), "invalid_auth"),
        (SkiResortApiError("no resort", 404), "unknown_resort"),
        (SkiResortConnectionError("down"), "cannot_connect"),
    ],
)
async def test_user_flow_errors(hass: HomeAssistant, side_effect, expected):
    """Each client error maps to the right form error and re-shows the form."""
    with _patch_client(side_effect=side_effect):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_user_flow_duplicate_aborts(hass: HomeAssistant):
    """A resort already configured (same slug) aborts."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="vail",
        data={CONF_API_KEY: "key", CONF_RESORT: "Vail", CONF_NAME: "Vail"},
    ).add_to_hass(hass)
    with _patch_client():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_success(hass: HomeAssistant):
    """Reauth validates a new key and updates the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="vail",
        data={CONF_API_KEY: "old", CONF_RESORT: "Vail", CONF_NAME: "Vail"},
        options={CONF_UNITS: UNIT_IMPERIAL},
    )
    entry.add_to_hass(hass)
    with _patch_client(), patch(
        "custom_components.ski_resort.async_setup_entry", return_value=True
    ):
        result = await entry.start_reauth_flow(hass)
        assert result["step_id"] == "reauth_confirm"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "new"}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new"


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (SkiResortAuthError("bad"), "invalid_auth"),
        (SkiResortApiError("no", 404), "unknown_resort"),
        (SkiResortConnectionError("down"), "cannot_connect"),
    ],
)
async def test_reauth_errors(hass: HomeAssistant, side_effect, expected):
    """Each client error during reauth re-shows the reauth form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="vail",
        data={CONF_API_KEY: "old", CONF_RESORT: "Vail", CONF_NAME: "Vail"},
    )
    entry.add_to_hass(hass)
    with _patch_client(side_effect=side_effect):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "new"}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_options_flow_defaults_slug_from_resort(hass: HomeAssistant):
    """With no stored slug, the option defaults to the resort's slug."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="beaver-creek",
        data={CONF_API_KEY: "key", CONF_RESORT: "Beaver Creek", CONF_NAME: "BC"},
        options={CONF_UNITS: UNIT_IMPERIAL},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    schema = result["data_schema"].schema
    slug_default = next(
        marker.default() for marker in schema if marker.schema == CONF_LIFT_SLUG
    )
    assert slug_default == "beaver-creek"


async def test_options_flow_submit(hass: HomeAssistant):
    """Submitting the options form persists the values (stored slug branch)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="vail",
        data={CONF_API_KEY: "key", CONF_RESORT: "Vail", CONF_NAME: "Vail"},
        options={CONF_UNITS: UNIT_IMPERIAL, CONF_LIFT_SLUG: "vail"},
    )
    entry.add_to_hass(hass)
    new_opts = {
        CONF_SCAN_INTERVAL_MINUTES: 120,
        CONF_UNITS: UNIT_IMPERIAL,
        CONF_ELEVATION: "mid",
        CONF_ENABLE_LIFTS: True,
        CONF_LIFT_SLUG: "vail",
    }
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], new_opts
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ELEVATION] == "mid"
    assert entry.options[CONF_ENABLE_LIFTS] is True
