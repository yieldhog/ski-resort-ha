"""Config/options flow tests (held to 100% coverage)."""

from __future__ import annotations

from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ski_resort.const import (
    CONF_COUNTRY,
    CONF_FORECAST_RESORT,
    CONF_LIFT_SLUG,
    CONF_LIFTIE_BASE_URL,
    CONF_NAME,
    CONF_QUERY,
    CONF_RAPIDAPI_KEY,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_SKI_AREA,
    CONF_UNITS,
    DOMAIN,
    UNIT_IMPERIAL,
    UNIT_METRIC,
)

AREA = {"id": "vailid", "name": "Vail", "country": "United States",
        "region": "Colorado", "lifts": 32}
BARE = {"id": "bareid", "name": None, "country": None, "region": None, "lifts": 0}


def _patch_data(matches=(AREA,), area=AREA, slug="vail"):
    """Patch the data-module functions the flow calls (sync, via executor)."""
    return (
        patch("custom_components.ski_resort.data.countries",
              new=Mock(return_value=["United States", "Canada"])),
        patch("custom_components.ski_resort.data.search_areas",
              new=Mock(return_value=list(matches))),
        patch("custom_components.ski_resort.data.get_area",
              new=Mock(return_value=area)),
        patch("custom_components.ski_resort.data.liftie_slug_for",
              new=Mock(return_value=slug)),
    )


async def test_full_flow(hass: HomeAssistant):
    """Query -> select -> entry, with auto slug and default units."""
    p1, p2, p3, p4 = _patch_data()
    with p1, p2, p3, p4, patch(
        "custom_components.ski_resort.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_QUERY: "vail", CONF_COUNTRY: "United States"}
        )
        assert result["step_id"] == "select"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SKI_AREA: "vailid"}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vail"
    assert result["data"]["id"] == "vailid"
    assert result["options"][CONF_LIFT_SLUG] == "vail"
    assert result["options"][CONF_UNITS] == UNIT_IMPERIAL


async def test_no_results(hass: HomeAssistant):
    """An empty search re-shows the user step with an error."""
    p1, p2, p3, p4 = _patch_data(matches=())
    with p1, p2, p3, p4:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_QUERY: "zzz"}
        )
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_results"}


async def test_name_override_and_bare_label(hass: HomeAssistant):
    """A display-name override wins; a nameless/liftless area still labels."""
    p1, p2, p3, p4 = _patch_data(matches=(BARE,), area=BARE, slug=None)
    with p1, p2, p3, p4, patch(
        "custom_components.ski_resort.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_QUERY: "x"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SKI_AREA: "bareid", CONF_NAME: "My hill"}
        )
    assert result["title"] == "My hill"
    assert result["options"][CONF_LIFT_SLUG] == ""


async def test_duplicate_aborts(hass: HomeAssistant):
    """Re-adding the same OpenSkiMap id aborts."""
    MockConfigEntry(domain=DOMAIN, unique_id="vailid",
                    data={"id": "vailid", "name": "Vail", "area": AREA}).add_to_hass(hass)
    p1, p2, p3, p4 = _patch_data()
    with p1, p2, p3, p4:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_QUERY: "vail"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SKI_AREA: "vailid"}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant):
    """Options persist; blank optional strings are dropped."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="vailid",
        data={"id": "vailid", "name": "Vail", "area": AREA},
        options={CONF_UNITS: UNIT_IMPERIAL, CONF_LIFT_SLUG: "vail"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL_MINUTES: 120,
            CONF_UNITS: UNIT_METRIC,
            CONF_LIFT_SLUG: "vail",
            CONF_LIFTIE_BASE_URL: "",  # blank -> dropped
            CONF_RAPIDAPI_KEY: "abc",
            CONF_FORECAST_RESORT: "Vail",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_UNITS] == UNIT_METRIC
    assert entry.options[CONF_RAPIDAPI_KEY] == "abc"
    assert CONF_LIFTIE_BASE_URL not in entry.options  # blank dropped


async def test_select_area_vanished_aborts(hass: HomeAssistant):
    """If the picked area is no longer in the index, the flow aborts cleanly."""
    p1, p2, p3, p4 = _patch_data(area=None)
    with p1, p2, p3, p4:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_QUERY: "vail"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SKI_AREA: "vailid"}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "area_not_found"


async def test_options_invalid_liftie_url(hass: HomeAssistant):
    """A Liftie base URL without a scheme is rejected."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="vailid",
        data={"id": "vailid", "name": "Vail", "area": AREA},
        options={CONF_UNITS: UNIT_IMPERIAL},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL_MINUTES: 60,
            CONF_UNITS: UNIT_IMPERIAL,
            CONF_LIFTIE_BASE_URL: "homeassistant.local:3000",  # no scheme
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_LIFTIE_BASE_URL: "invalid_url"}


async def test_options_invalid_webcam_url(hass: HomeAssistant):
    """A webcam URL without a scheme is rejected, keyed to the webcam field."""
    from custom_components.ski_resort.const import CONF_WEBCAM_URL

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="vailid",
        data={"id": "vailid", "name": "Vail", "area": AREA},
        options={CONF_UNITS: UNIT_IMPERIAL},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL_MINUTES: 60,
            CONF_UNITS: UNIT_IMPERIAL,
            CONF_WEBCAM_URL: "cam.example/live.jpg",  # no scheme
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_WEBCAM_URL: "invalid_url"}
