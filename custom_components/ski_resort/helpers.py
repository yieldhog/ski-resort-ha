"""Pure helper functions for the Ski Resort Forecast integration.

No Home Assistant imports here, so these stay trivially unit-testable. They
absorb the quirks of the RapidAPI payloads: measurements arrive as strings with
a unit suffix ("83in", "210 cm"), sometimes ``null``; dates arrive as
human-readable "25 Jan 2026".
"""

from __future__ import annotations

import re
from datetime import date, datetime

# First signed decimal number anywhere in a string ("83in" -> 83, "-1.5cm" ->
# -1.5). Anchored to a digit run so unit letters and stray spaces are ignored.
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_measure(value: object) -> float | None:
    """Parse a snow measurement to a float, or ``None`` when absent/unusable.

    The forecast API returns depths/snowfall as unit-suffixed strings ("83in",
    "210 cm") and ``null`` when a value is unavailable. Numbers pass straight
    through; anything without a parseable number becomes ``None`` so a missing
    reading shows as *unavailable* rather than a misleading ``0``.
    """
    if value is None:
        return None
    if isinstance(value, bool):  # bool is an int subclass; never a measurement
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = _NUMBER_RE.search(value)
    return float(match.group()) if match else None


def parse_snow_date(value: object) -> date | None:
    """Parse a "25 Jan 2026" style date to a ``date``, or ``None``.

    Returns ``None`` for empty/``null``/unparseable input so a
    ``device_class: date`` sensor reports *unavailable* instead of erroring.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d %b %Y").date()
    except ValueError:
        return None


def slugify_resort(name: str) -> str:
    """Best-effort default lift-status slug from a forecast resort name.

    The conditions (skiapi) product keys resorts by a lowercase, hyphenated
    slug ("Beaver Creek" -> "beaver-creek"). This is only a starting suggestion
    in the options flow; the user can override it.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return slug.strip("-")


def trend_of(current: float | None, previous: float | None) -> str | None:
    """Classify a change between two readings as up/down/stable.

    ``None`` when either side is missing (no basis for comparison). Equal
    readings are ``stable``; this is deliberately exact — the caller decides
    any tolerance before calling.
    """
    if current is None or previous is None:
        return None
    if current > previous:
        return "up"
    if current < previous:
        return "down"
    return "stable"
