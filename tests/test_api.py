"""Tests for the shared HTTP helper and source clients."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from custom_components.ski_resort.api import (
    SkiResortApiError,
    SkiResortAuthError,
    SkiResortConnectionError,
    async_liftie,
    async_open_meteo,
    async_skiapi,
)


def _patch_get(hass, response=None, side_effect=None):
    """Patch the shared httpx client's get to return a fixed response."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=response, side_effect=side_effect)
    return patch(
        "custom_components.ski_resort.api.get_async_client", return_value=client
    ), client


async def test_open_meteo_ok(hass):
    patcher, _ = _patch_get(hass, httpx.Response(200, json={"current": {"t": 1}}))
    with patcher:
        assert await async_open_meteo(hass, 39.6, -106.3) == {"current": {"t": 1}}


async def test_non_dict_body_is_empty(hass):
    patcher, _ = _patch_get(hass, httpx.Response(200, json=[1, 2]))
    with patcher:
        assert await async_open_meteo(hass, 1, 2) == {}


async def test_auth_error(hass):
    patcher, _ = _patch_get(hass, httpx.Response(403))
    with patcher, pytest.raises(SkiResortAuthError):
        await async_skiapi(hass, "key", "vail")


async def test_api_error_status(hass):
    patcher, _ = _patch_get(hass, httpx.Response(404))
    with patcher, pytest.raises(SkiResortApiError) as exc:
        await async_liftie(hass, "http://liftie.local", "nope")
    assert exc.value.status_code == 404


async def test_transport_error(hass):
    patcher, _ = _patch_get(hass, side_effect=httpx.ConnectError("boom"))
    with patcher, pytest.raises(SkiResortConnectionError) as exc:
        await async_open_meteo(hass, 1, 2)
    assert not isinstance(exc.value, SkiResortApiError)


async def test_retry_then_success(hass, monkeypatch):
    import custom_components.ski_resort.api as api_mod

    monkeypatch.setattr(api_mod, "_RETRY_BACKOFF", 0)
    patcher, client = _patch_get(hass)
    client.get = AsyncMock(
        side_effect=[httpx.Response(500), httpx.Response(200, json={"ok": 1})]
    )
    with patcher:
        assert await async_open_meteo(hass, 1, 2) == {"ok": 1}
    assert client.get.call_count == 2


async def test_429_not_retried(hass):
    """A 429 (quota/rate limit) fails immediately without burning extra calls."""
    patcher, client = _patch_get(hass, httpx.Response(429))
    with patcher, pytest.raises(SkiResortApiError) as exc:
        await async_skiapi(hass, "key", "vail")
    assert exc.value.status_code == 429
    assert client.get.call_count == 1  # no retry


async def test_empty_body_none(hass):
    patcher, _ = _patch_get(hass, httpx.Response(204))
    with patcher:
        assert await async_open_meteo(hass, 1, 2) == {}


async def test_bad_json(hass):
    patcher, _ = _patch_get(hass, httpx.Response(200, content=b"xx"))
    with patcher, pytest.raises(SkiResortApiError):
        await async_open_meteo(hass, 1, 2)


async def test_liftie_strips_trailing_slash(hass):
    patcher, client = _patch_get(hass, httpx.Response(200, json={"lifts": {}}))
    with patcher:
        await async_liftie(hass, "http://liftie.local/", "vail")
    called_url = client.get.call_args.args[0]
    assert called_url == "http://liftie.local/api/resort/vail"


async def test_liftie_tolerates_full_api_url(hass):
    """A base URL that already includes /api/resort/... is trimmed to the root."""
    patcher, client = _patch_get(hass, httpx.Response(200, json={"lifts": {}}))
    with patcher:
        await async_liftie(hass, "http://host:3000/api/resort/vail", "vail")
    called_url = client.get.call_args.args[0]
    assert called_url == "http://host:3000/api/resort/vail"  # not doubled


async def test_skiapi_and_rapidapi_snow_shapes(hass):
    """skiapi and rapidapi-snow return their JSON dicts (cover both clients)."""
    from custom_components.ski_resort.api import async_rapidapi_snow

    patcher, _ = _patch_get(hass, httpx.Response(200, json={"data": {"lifts": {}}}))
    with patcher:
        assert await async_skiapi(hass, "k", "vail") == {"data": {"lifts": {}}}
    patcher2, _ = _patch_get(hass, httpx.Response(200, json={"topSnowDepth": "80in"}))
    with patcher2:
        got = await async_rapidapi_snow(hass, "k", "Vail", "i")
    assert got == {"topSnowDepth": "80in"}


async def test_nws_alerts_returns_features_with_user_agent(hass):
    from custom_components.ski_resort.api import async_nws_alerts

    body = {"features": [{"properties": {"event": "Winter Storm Warning"}}]}
    patcher, client = _patch_get(hass, httpx.Response(200, json=body))
    with patcher:
        features = await async_nws_alerts(hass, 39.6, -106.35)
    assert features == body["features"]
    # NWS requires a descriptive User-Agent; the point param is "lat,lon".
    kwargs = client.get.call_args.kwargs
    assert kwargs["headers"]["User-Agent"]
    assert kwargs["params"]["point"] == "39.6,-106.35"


async def test_nws_alerts_non_dict_body_is_empty(hass):
    from custom_components.ski_resort.api import async_nws_alerts

    patcher, _ = _patch_get(hass, httpx.Response(200, json=[1, 2]))
    with patcher:
        assert await async_nws_alerts(hass, 1, 2) == []


async def test_avalanche_map_layer_center_path(hass):
    from custom_components.ski_resort.api import async_avalanche_map_layer

    patcher, client = _patch_get(hass, httpx.Response(200, json={"features": []}))
    with patcher:
        await async_avalanche_map_layer(hass, "CAIC")
    assert client.get.call_args.args[0].endswith("/map-layer/CAIC")
    # No center -> the global layer (used for auto-detection).
    patcher2, client2 = _patch_get(hass, httpx.Response(200, json={"features": []}))
    with patcher2:
        await async_avalanche_map_layer(hass)
    assert client2.get.call_args.args[0].endswith("/map-layer")


async def test_avalanche_canada_clients(hass):
    from custom_components.ski_resort.api import (
        async_avalanche_ca_areas,
        async_avalanche_ca_metadata,
    )

    patcher, client = _patch_get(hass, httpx.Response(200, json={"features": []}))
    with patcher:
        assert await async_avalanche_ca_areas(hass) == {"features": []}
    assert client.get.call_args.args[0].endswith("/forecasts/en/areas")

    patcher2, client2 = _patch_get(hass, httpx.Response(200, json=[{"area": {}}]))
    with patcher2:
        assert await async_avalanche_ca_metadata(hass) == [{"area": {}}]
    assert client2.get.call_args.args[0].endswith("/forecasts/en/metadata")
    # A non-list body degrades to an empty list.
    patcher3, _ = _patch_get(hass, httpx.Response(200, json={"x": 1}))
    with patcher3:
        assert await async_avalanche_ca_metadata(hass) == []


async def test_wikidata_item(hass):
    from custom_components.ski_resort.api import async_wikidata_item

    patcher, _ = _patch_get(hass, httpx.Response(200, json={"statements": {"P18": []}}))
    with patcher:
        assert await async_wikidata_item(hass, "Q1") == {"statements": {"P18": []}}


async def test_skimap_trailmap_parses_og_image(hass):
    from custom_components.ski_resort.api import async_skimap_trailmap

    html = '<meta property="og:image" content="https://files.skimap.org/abc">'
    patcher, _ = _patch_get(hass, httpx.Response(200, text=html))
    with patcher:
        assert await async_skimap_trailmap(hass, 507) == "https://files.skimap.org/abc"


async def test_skimap_trailmap_none_cases(hass):
    from custom_components.ski_resort.api import async_skimap_trailmap

    patcher, _ = _patch_get(hass, httpx.Response(301))  # redirect/error status
    with patcher:
        assert await async_skimap_trailmap(hass, 1) is None
    patcher2, _ = _patch_get(hass, httpx.Response(200, text="<html>no og</html>"))
    with patcher2:
        assert await async_skimap_trailmap(hass, 1) is None


async def test_skimap_trailmap_transport_error(hass):
    from custom_components.ski_resort.api import (
        SkiResortConnectionError,
        async_skimap_trailmap,
    )

    patcher, _ = _patch_get(hass, side_effect=httpx.ConnectError("boom"))
    with patcher, pytest.raises(SkiResortConnectionError):
        await async_skimap_trailmap(hass, 1)
