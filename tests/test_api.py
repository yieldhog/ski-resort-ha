"""Tests for the RapidAPI client's error mapping and retry behaviour."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from custom_components.ski_resort.api import (
    SkiResortApiError,
    SkiResortAuthError,
    SkiResortClient,
    SkiResortConnectionError,
)


def _client_returning(hass, response: httpx.Response) -> SkiResortClient:
    """Build a client whose underlying httpx GET returns a fixed response."""
    client = SkiResortClient(hass, "key")
    client._client = AsyncMock()
    client._client.get = AsyncMock(return_value=response)
    return client


async def test_snow_conditions_parses_json(hass):
    """A 200 with a JSON body returns the parsed dict."""
    client = _client_returning(
        hass, httpx.Response(200, json={"freshSnowfall": "5in"})
    )
    data = await client.async_get_snow_conditions("Vail", "i")
    assert data == {"freshSnowfall": "5in"}


async def test_non_dict_body_becomes_empty_dict(hass):
    """A JSON list where a dict is expected degrades to {} (never crashes)."""
    client = _client_returning(hass, httpx.Response(200, json=["unexpected"]))
    assert await client.async_get_snow_conditions("Vail", "i") == {}


async def test_401_maps_to_auth_error(hass):
    """A rejected key raises the dedicated auth error."""
    client = _client_returning(hass, httpx.Response(401))
    with pytest.raises(SkiResortAuthError):
        await client.async_get_forecast("Vail", "i", "top")


async def test_404_maps_to_api_error(hass):
    """An unknown resort (404) is an API error carrying the status code."""
    client = _client_returning(hass, httpx.Response(404, json={"message": "no"}))
    with pytest.raises(SkiResortApiError) as exc:
        await client.async_get_snow_conditions("Nowhere", "i")
    assert exc.value.status_code == 404
    assert isinstance(exc.value, SkiResortConnectionError)


async def test_transport_error_maps_to_connection_error(hass):
    """An httpx transport failure is a plain connection error."""
    client = SkiResortClient(hass, "key")
    client._client = AsyncMock()
    client._client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(SkiResortConnectionError) as exc:
        await client.async_get_lift_status("vail")
    assert not isinstance(exc.value, SkiResortApiError)


async def test_empty_body_is_none(hass):
    """A 204 / empty body is treated as no data (None)."""
    client = _client_returning(hass, httpx.Response(204))
    assert await client.async_get_snow_conditions("Vail", "i") == {}


async def test_transient_500_is_retried_then_succeeds(hass, monkeypatch):
    """A transient 5xx is retried; a good response on a later attempt wins."""
    import custom_components.ski_resort.api as api_mod

    monkeypatch.setattr(api_mod, "_RETRY_BACKOFF", 0)  # no real delay in tests
    client = SkiResortClient(hass, "key")
    client._client = AsyncMock()
    client._client.get = AsyncMock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(200, json={"topSnowDepth": "80in"}),
        ]
    )
    data = await client.async_get_snow_conditions("Vail", "i")
    assert data == {"topSnowDepth": "80in"}
    assert client._client.get.call_count == 2


async def test_persistent_500_raises_after_retries(hass, monkeypatch):
    """A 5xx that never clears eventually raises an API error."""
    import custom_components.ski_resort.api as api_mod

    monkeypatch.setattr(api_mod, "_RETRY_BACKOFF", 0)
    client = _client_returning(hass, httpx.Response(503))
    with pytest.raises(SkiResortApiError) as exc:
        await client.async_get_forecast("Vail", "i", "top")
    assert exc.value.status_code == 503


async def test_bad_json_raises_api_error(hass):
    """A 200 with an unparseable body is an API error, not silent None."""
    client = _client_returning(
        hass, httpx.Response(200, content=b"not json", headers={})
    )
    with pytest.raises(SkiResortApiError):
        await client.async_get_snow_conditions("Vail", "i")


async def test_validate_resort_delegates_to_snow(hass):
    """async_validate_resort returns the snow-conditions dict on success."""
    client = _client_returning(
        hass, httpx.Response(200, json={"topSnowDepth": "80in"})
    )
    assert await client.async_validate_resort("Vail", "i") == {"topSnowDepth": "80in"}
