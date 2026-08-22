"""Pure helpers (no Home Assistant imports) for the Ski Resort integration."""

from __future__ import annotations

import re
from datetime import date, datetime
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


def sum_next_hours(times: list[Any], values: list[Any], hours: int) -> float | None:
    """Sum the next ``hours`` hourly values starting at the current hour.

    Open-Meteo returns aligned ``time``/value arrays; this sums the first
    ``hours`` valid numbers (a simple, timezone-agnostic "next 24h" total).
    Returns ``None`` if there is nothing usable.
    """
    if not isinstance(values, list) or not values:
        return None
    total = 0.0
    seen = False
    for value in values[:hours]:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total += value
            seen = True
    return round(total, 2) if seen else None
