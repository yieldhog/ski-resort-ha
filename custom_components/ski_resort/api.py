"""Async client for the RapidAPI ski-resort endpoints.

Thin wrapper over Home Assistant's shared httpx client. A single RapidAPI key
unlocks two products; the ``X-RapidAPI-Host`` header per request selects which:

* ``ski-resort-forecast`` — snow conditions and the 3/5-day forecast (core).
* ``ski-resorts-and-conditions`` (skiapi) — live lift counts (optional).

Error model mirrors the shape a coordinator wants: auth failures are distinct
from transport failures, and a reached-but-errored response is its own type so
the config flow can give a resort-not-found hint without treating it as a
network outage.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import quote

import httpx
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONDITIONS_HOST, FORECAST_HOST

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = 20.0

# RapidAPI surfaces upstream hiccups and its own throttling as 429/5xx. These
# are transient, so retry a few times with exponential backoff before failing.
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF = 0.5  # seconds; doubled each retry (0.5s, 1.0s)

# One refresh fetches at most snow + forecast (+ lifts). Keep a small ceiling so
# a resort with lifts enabled never bursts the free-tier rate limit at once.
_MAX_CONCURRENCY = 2


class SkiResortError(Exception):
    """Base error for the ski-resort client."""


class SkiResortAuthError(SkiResortError):
    """Raised when the RapidAPI key is missing/invalid (401/403)."""


class SkiResortConnectionError(SkiResortError):
    """Raised when the API can't be reached (transport / network error)."""


class SkiResortApiError(SkiResortConnectionError):
    """Reached the API, but the response was an error or unusable.

    Distinct from a transport failure: a 404 here means an unknown resort
    name/slug, not an outage. Subclasses ``SkiResortConnectionError`` so a
    coordinator's ``UpdateFailed`` path still catches it, while the config flow
    can catch it first for a "check the resort name" message. Carries the HTTP
    status when known.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Store the human message and originating HTTP status (if any)."""
        super().__init__(message)
        self.status_code = status_code


class SkiResortClient:
    """Minimal async client for the endpoints this integration uses."""

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        """Store the shared httpx client and the RapidAPI key."""
        self._client = get_async_client(hass)
        self._api_key = api_key
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)

    def _headers(self, host: str) -> dict[str, str]:
        return {"X-RapidAPI-Key": self._api_key, "X-RapidAPI-Host": host}

    async def _get(
        self, host: str, path: str, params: dict[str, str] | None = None
    ) -> Any:
        """GET a RapidAPI endpoint and return parsed JSON.

        204/empty bodies become ``None`` (the caller decides what an empty
        section means). 401/403 raise auth; retryable statuses back off; any
        other error status or unparseable body raises ``SkiResortApiError``.
        """
        url = f"https://{host}/{path.lstrip('/')}"
        for attempt in range(_MAX_ATTEMPTS):
            # Hold the slot only across the network call, not the backoff sleep,
            # so a retrying request doesn't idle a concurrency slot.
            async with self._semaphore:
                try:
                    resp = await self._client.get(
                        url,
                        headers=self._headers(host),
                        params=params,
                        timeout=_TIMEOUT,
                    )
                except httpx.HTTPError as err:
                    raise SkiResortConnectionError(
                        f"Request to {path} failed: {err}"
                    ) from err

            if resp.status_code in (401, 403):
                raise SkiResortAuthError(
                    f"RapidAPI key rejected for {path} ({resp.status_code})"
                )
            # Error statuses are handled before the empty-body check below: a
            # 500 often comes back with no body, and that must retry/raise
            # rather than be mistaken for an empty (but successful) section.
            if resp.status_code in _RETRY_STATUSES and attempt < _MAX_ATTEMPTS - 1:
                delay = _RETRY_BACKOFF * (2**attempt)
                _LOGGER.debug(
                    "Ski resort %s returned HTTP %s; retrying in %.1fs (%d/%d)",
                    path,
                    resp.status_code,
                    delay,
                    attempt + 1,
                    _MAX_ATTEMPTS,
                )
                await asyncio.sleep(delay)
                continue
            if resp.status_code >= 300:
                _LOGGER.debug(
                    "Ski resort %s returned HTTP %s: %s",
                    path,
                    resp.status_code,
                    resp.text[:200],
                )
                raise SkiResortApiError(
                    f"{path} returned HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )
            # A 2xx with no body means the section is empty (e.g. no lift data);
            # let the caller decide what that means.
            if resp.status_code == 204 or not resp.content:
                return None
            try:
                return resp.json()
            except ValueError as err:
                _LOGGER.debug(
                    "Ski resort %s returned an unparseable body: %s",
                    path,
                    resp.text[:200],
                )
                raise SkiResortApiError(
                    f"Bad JSON from {path}: {err}", status_code=resp.status_code
                ) from err

    @staticmethod
    def _as_dict(data: Any) -> dict[str, Any]:
        return data if isinstance(data, dict) else {}

    # --- Forecast product --------------------------------------------------
    async def async_get_snow_conditions(
        self, resort: str, units: str
    ) -> dict[str, Any]:
        """GET /{resort}/snowConditions — depths, fresh snow, last-snow date."""
        return self._as_dict(
            await self._get(
                FORECAST_HOST,
                f"{quote(resort)}/snowConditions",
                {"units": units},
            )
        )

    async def async_get_forecast(
        self, resort: str, units: str, elevation: str
    ) -> dict[str, Any]:
        """GET /{resort}/forecast — 3/5-day summary, forecast5Day, basicInfo."""
        return self._as_dict(
            await self._get(
                FORECAST_HOST,
                f"{quote(resort)}/forecast",
                {"units": units, "el": elevation},
            )
        )

    # --- Conditions product (optional) -------------------------------------
    async def async_get_lift_status(self, slug: str) -> dict[str, Any]:
        """GET /v1/resort/{slug} — resort record incl. lift stats (skiapi)."""
        return self._as_dict(
            await self._get(CONDITIONS_HOST, f"v1/resort/{quote(slug)}")
        )

    # --- Validation --------------------------------------------------------
    async def async_validate_resort(self, resort: str, units: str) -> dict[str, Any]:
        """Confirm the key + resort name by fetching snow conditions.

        Returns the (possibly empty) snow-conditions dict so the flow can reuse
        it. Raises ``SkiResortAuthError`` on a bad key or ``SkiResortApiError``
        on an unknown resort.
        """
        return await self.async_get_snow_conditions(resort, units)
