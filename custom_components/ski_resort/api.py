"""HTTP clients for the Ski Resort integration's data sources.

Each source is a small async function over Home Assistant's shared httpx client,
sharing one retry/backoff helper:

* Open-Meteo (``api.open-meteo.com``) — free, keyless weather + snow by lat/lon.
* Liftie (a self-hosted base URL) — free lift status, ``/api/resort/<slug>``.
* skiapi (RapidAPI ``ski-resorts-and-conditions``) — the same Liftie data,
  proxied; needs a RapidAPI key.
* RapidAPI snow-forecast — optional snow depths + 3-day prose summary.

Errors mirror what a coordinator wants: auth (key rejected) vs. connection
(transport) vs. api (reached but errored, e.g. unknown resort).
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    AVALANCHE_HOST,
    CONDITIONS_HOST,
    FORECAST_HOST,
    NWS_HOST,
    NWS_USER_AGENT,
    OPEN_METEO_HOST,
    SKIMAP_HOST,
    WIKIDATA_HOST,
)

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = 20.0
# Retry only transient *server* errors. 429 (rate/quota limit) is deliberately
# excluded: retrying a quota-limited API (e.g. RapidAPI's metered plans) can't
# succeed and just burns more of the allowance, so we fail fast instead.
_RETRY_STATUSES = frozenset({500, 502, 503, 504})
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF = 0.5


class SkiResortError(Exception):
    """Base error."""


class SkiResortAuthError(SkiResortError):
    """A RapidAPI key was missing/rejected (401/403)."""


class SkiResortConnectionError(SkiResortError):
    """The source could not be reached (transport error)."""


class SkiResortApiError(SkiResortConnectionError):
    """Reached the source but the response was an error/unusable."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Store message and originating HTTP status."""
        super().__init__(message)
        self.status_code = status_code


async def _get_json(
    hass: HomeAssistant,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """GET ``url`` and return parsed JSON, with retry/backoff on 429/5xx.

    401/403 raise :class:`SkiResortAuthError`; transport failures raise
    :class:`SkiResortConnectionError`; other error statuses or bad bodies raise
    :class:`SkiResortApiError`. A 204/empty body returns ``None``.
    """
    client = get_async_client(hass)
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = await client.get(
                url, headers=headers, params=params, timeout=_TIMEOUT
            )
        except (httpx.HTTPError, httpx.InvalidURL) as err:
            # InvalidURL is not an HTTPError subclass; a mistyped Liftie base URL
            # (e.g. missing scheme) lands here and must degrade, not crash.
            raise SkiResortConnectionError(f"Request to {url} failed: {err}") from err

        if resp.status_code in (401, 403):
            raise SkiResortAuthError(f"Key rejected ({resp.status_code})")
        if resp.status_code == 429:
            # Rate/quota limit — not retried (see _RETRY_STATUSES). Surface a
            # clear message; the coordinator degrades this source to None.
            raise SkiResortApiError(
                f"Rate or quota limit reached (429) at {url}", status_code=429
            )
        if resp.status_code in _RETRY_STATUSES and attempt < _MAX_ATTEMPTS - 1:
            await asyncio.sleep(_RETRY_BACKOFF * (2**attempt))
            continue
        if resp.status_code >= 300:
            raise SkiResortApiError(
                f"HTTP {resp.status_code} from {url}", status_code=resp.status_code
            )
        if resp.status_code == 204 or not resp.content:
            return None
        try:
            return resp.json()
        except ValueError as err:
            raise SkiResortApiError(f"Bad JSON from {url}: {err}") from err


# --- Open-Meteo (free, keyless) -------------------------------------------
async def async_open_meteo(
    hass: HomeAssistant, lat: float, lon: float
) -> dict[str, Any]:
    """Fetch current + hourly + daily weather/snow (SI units) for a point."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,relative_humidity_2m,weather_code,"
            "wind_speed_10m,wind_gusts_10m,snowfall"
        ),
        "hourly": "snowfall,snow_depth,freezing_level_height",
        "daily": (
            "weather_code,temperature_2m_max,temperature_2m_min,"
            "snowfall_sum,precipitation_sum,wind_speed_10m_max,"
            "wind_gusts_10m_max,sunrise,sunset"
        ),
        "timezone": "auto",
        "forecast_days": 7,
    }
    data = await _get_json(
        hass, f"https://{OPEN_METEO_HOST}/v1/forecast", params=params
    )
    return data if isinstance(data, dict) else {}


# --- Liftie (self-hosted) --------------------------------------------------
async def async_liftie(
    hass: HomeAssistant, base_url: str, slug: str
) -> dict[str, Any]:
    """Fetch ``<base_url>/api/resort/<slug>`` from a Liftie instance.

    Tolerant of a base URL that already includes an ``/api/...`` path: pasting a
    full endpoint like ``http://host:3000/api/resort/vail`` is trimmed back to
    the server root so the request isn't doubled up (``.../api/resort/vail/api/
    resort/vail``).
    """
    base = base_url.rstrip("/")
    api_index = base.find("/api/")
    if api_index != -1:
        base = base[:api_index]
    data = await _get_json(hass, f"{base}/api/resort/{quote(slug)}")
    return data if isinstance(data, dict) else {}


# --- skiapi (RapidAPI; = Liftie data) --------------------------------------
async def async_skiapi(hass: HomeAssistant, key: str, slug: str) -> dict[str, Any]:
    """Fetch RapidAPI ski-resorts-and-conditions ``/v1/resort/<slug>``."""
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": CONDITIONS_HOST}
    data = await _get_json(
        hass, f"https://{CONDITIONS_HOST}/v1/resort/{quote(slug)}", headers=headers
    )
    return data if isinstance(data, dict) else {}


# --- RapidAPI snow-forecast (optional) -------------------------------------
async def async_rapidapi_snow(
    hass: HomeAssistant, key: str, resort: str, units: str
) -> dict[str, Any]:
    """Fetch RapidAPI snow-forecast ``/<resort>/snowConditions``."""
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": FORECAST_HOST}
    data = await _get_json(
        hass,
        f"https://{FORECAST_HOST}/{quote(resort)}/snowConditions",
        headers=headers,
        params={"units": units},
    )
    return data if isinstance(data, dict) else {}


# --- NWS weather alerts (US, public domain) --------------------------------
async def async_nws_alerts(
    hass: HomeAssistant, lat: float, lon: float
) -> list[dict[str, Any]]:
    """Fetch active NWS alerts for a point; returns the alert feature list.

    api.weather.gov requires a descriptive User-Agent on every request. US-only;
    a point outside NWS coverage simply returns no features.
    """
    data = await _get_json(
        hass,
        f"https://{NWS_HOST}/alerts/active",
        headers={"User-Agent": NWS_USER_AGENT, "Accept": "application/geo+json"},
        params={"point": f"{lat},{lon}"},
    )
    features = data.get("features") if isinstance(data, dict) else None
    return features if isinstance(features, list) else []


# --- Avalanche danger (avalanche.org, keyless) -----------------------------
async def async_avalanche_map_layer(
    hass: HomeAssistant, center_id: str | None = None
) -> dict[str, Any]:
    """Fetch the avalanche.org map-layer GeoJSON (all centers, or one center).

    Passing a ``center_id`` fetches just that center's zones (smaller); omitting
    it returns every US center, used once to auto-detect which center a resort
    falls in.
    """
    path = "/v2/public/products/map-layer"
    if center_id:
        path += f"/{quote(center_id)}"
    data = await _get_json(hass, f"https://{AVALANCHE_HOST}{path}")
    return data if isinstance(data, dict) else {}


# --- Enrichment: Wikidata (CC0) --------------------------------------------
async def async_wikidata_item(hass: HomeAssistant, qid: str) -> dict[str, Any]:
    """Fetch a Wikidata item's statements via the REST API (keyless, CC0)."""
    data = await _get_json(
        hass,
        f"https://{WIKIDATA_HOST}/w/rest.php/wikibase/v1/entities/items/{quote(qid)}",
    )
    return data if isinstance(data, dict) else {}


# --- Enrichment: skimap.org trail map (og:image) ---------------------------
async def async_skimap_trailmap(hass: HomeAssistant, skimap_id: int) -> str | None:
    """Resolve a resort's trail-map image URL from its skimap.org page.

    skimap.org exposes the trail map as the page's ``og:image``; parse it out.
    Returns ``None`` if unavailable.
    """
    client = get_async_client(hass)
    url = f"https://{SKIMAP_HOST}/skiareas/view/{skimap_id}"
    try:
        resp = await client.get(url, timeout=_TIMEOUT, follow_redirects=True)
    except (httpx.HTTPError, httpx.InvalidURL) as err:
        raise SkiResortConnectionError(f"skimap {skimap_id}: {err}") from err
    if resp.status_code >= 300:
        return None
    match = re.search(
        r'property="og:image"\s+content="([^"]+)"', resp.text
    ) or re.search(r'content="([^"]+)"\s+property="og:image"', resp.text)
    return match.group(1) if match else None
