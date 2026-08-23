"""Pure helpers (no Home Assistant imports) for the Ski Resort integration."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

# WMO weather code -> Home Assistant condition string. Open-Meteo returns WMO
# codes; HA weather cards understand this fixed vocabulary.
_WMO_TO_CONDITION = {
    0: "sunny",
    1: "partlycloudy",
    2: "partlycloudy",
    3: "cloudy",
    45: "fog",
    48: "fog",
    51: "rainy",
    53: "rainy",
    55: "rainy",
    56: "snowy-rainy",
    57: "snowy-rainy",
    61: "rainy",
    63: "rainy",
    65: "pouring",
    66: "snowy-rainy",
    67: "snowy-rainy",
    71: "snowy",
    73: "snowy",
    75: "snowy",
    77: "snowy",
    80: "rainy",
    81: "rainy",
    82: "pouring",
    85: "snowy",
    86: "snowy",
    95: "lightning",
    96: "lightning-rainy",
    99: "lightning-rainy",
}

_CM_PER_INCH = 2.54
_M_PER_FOOT = 0.3048


def condition_from_wmo(code: object) -> str | None:
    """Map a WMO weather code to a Home Assistant condition, or ``None``."""
    if not isinstance(code, (int, float)) or isinstance(code, bool):
        return None
    return _WMO_TO_CONDITION.get(int(code))


def cm_to_display(value: float | None, imperial: bool) -> float | None:
    """Convert a centimetre value to inches when imperial; round sensibly."""
    if value is None:
        return None
    return round(value / _CM_PER_INCH, 1) if imperial else round(value, 1)


def m_to_depth_display(value: float | None, imperial: bool) -> float | None:
    """Convert a metre snow-depth to inches or centimetres for display."""
    if value is None:
        return None
    cm = value * 100.0
    return round(cm / _CM_PER_INCH, 1) if imperial else round(cm, 1)


def m_to_elev_display(value: float | None, imperial: bool) -> float | None:
    """Convert a metre elevation to feet (imperial) or metres."""
    if value is None:
        return None
    return round(value / _M_PER_FOOT) if imperial else round(value)


def parse_measure(value: object) -> float | None:
    """Parse a RapidAPI unit-suffixed measurement ("83in") to a float."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = _NUMBER_RE.search(value)
    return float(match.group()) if match else None


def parse_snow_date(value: object) -> date | None:
    """Parse a "25 Jan 2026" RapidAPI date to a ``date``, or ``None``."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%d %b %Y").date()
    except ValueError:
        return None


_OPENSNOW_CAM_RE = re.compile(r"opensnow\.com/location/[^/]+/cams/(\d+)", re.IGNORECASE)


def resolve_webcam_url(url: str) -> str:
    """Normalize a configured webcam URL to a direct still-image URL.

    A convenience for OpenSnow: pasting a cam *page* URL like
    ``https://opensnow.com/location/vail/cams/3380`` is rewritten to that cam's
    direct latest-frame image (``https://cams.opensnow.com/latest/3380/720.webp``).
    Any other URL is returned unchanged.
    """
    match = _OPENSNOW_CAM_RE.search(url or "")
    if match:
        return f"https://cams.opensnow.com/latest/{match.group(1)}/720.webp"
    return url


def local_now_marker(now_utc: datetime, utc_offset_seconds: object) -> str | None:
    """Resort-local hour marker ("YYYY-MM-DDTHH:00") for aligning hourly arrays.

    Open-Meteo (``timezone=auto``) returns naive hourly timestamps in the
    resort's local time; ``utc_offset_seconds`` in the same response gives the
    shift from UTC. This converts ``now_utc`` to that local wall clock, truncated
    to the top of the hour, so it can be compared against the hourly ``time``
    keys. Returns ``None`` when the offset is missing/unusable, in which case
    callers fall back to the start of the array.
    """
    if not isinstance(utc_offset_seconds, (int, float)) or isinstance(
        utc_offset_seconds, bool
    ):
        return None
    local = now_utc + timedelta(seconds=int(utc_offset_seconds))
    return local.strftime("%Y-%m-%dT%H:00")


def _start_index(times: list[Any], now: str | None) -> int:
    """Index of the first timestamp at/after ``now`` (0 if unknown/not found)."""
    if not now or not isinstance(times, list):
        return 0
    for i, moment in enumerate(times):
        if isinstance(moment, str) and moment >= now:
            return i
    return 0


def _point_in_ring(x: float, y: float, ring: list[Any]) -> bool:
    """Ray-casting point-in-polygon for a single GeoJSON ring ([[lon, lat], ...])."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        # The (yi > y) != (yj > y) guard also rules out yi == yj, so the divide
        # below can't hit a zero denominator.
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_geometry(lon: float, lat: float, geometry: Any) -> bool:
    """Whether (lon, lat) is inside a GeoJSON Polygon/MultiPolygon exterior ring.

    Used to find the avalanche-forecast zone a resort falls in. Holes are
    ignored (zones rarely have them, and a false positive is harmless here).
    """
    if not isinstance(geometry, dict):
        return False
    coords = geometry.get("coordinates") or []
    try:
        if geometry.get("type") == "Polygon":
            return bool(coords) and _point_in_ring(lon, lat, coords[0])
        if geometry.get("type") == "MultiPolygon":
            return any(poly and _point_in_ring(lon, lat, poly[0]) for poly in coords)
    except (TypeError, IndexError, ValueError):
        return False
    return False


def sum_next_hours(
    times: list[Any], values: list[Any], hours: int, now: str | None = None
) -> float | None:
    """Sum ``hours`` hourly values starting at the current hour.

    Open-Meteo returns aligned ``time``/value arrays beginning at 00:00 of the
    current local day, so a plain ``values[:hours]`` would total *today so far*
    rather than the *next* ``hours``. Given ``now`` (from :func:`local_now_marker`)
    the window starts at the current hour; without it, it falls back to the start
    of the array. Returns ``None`` if there is nothing usable.
    """
    if not isinstance(values, list) or not values:
        return None
    start = _start_index(times, now)
    total = 0.0
    seen = False
    for value in values[start : start + hours]:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total += value
            seen = True
    return round(total, 2) if seen else None


def value_at_hour(
    times: list[Any], values: list[Any], now: str | None = None
) -> float | None:
    """The hourly value at the current hour, or the first value as fallback.

    Aligns to ``now`` (from :func:`local_now_marker`) the same way as
    :func:`sum_next_hours`, so snapshot readings (snow depth, freezing level)
    reflect the current hour rather than midnight. Returns ``None`` if the
    aligned value is missing or non-numeric.
    """
    if not isinstance(values, list) or not values:
        return None
    start = _start_index(times, now)
    value = values[start] if start < len(values) else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None
