#!/usr/bin/env python3
"""Live canary: confirm snow-forecast.com still parses with our scraper.

The reported-depth sensors scrape snow-forecast.com, so a layout change there
could silently break them. This fetches a year-round glacier (which always has
a snow report) and runs the integration's *real* parser against today's page.
It exits non-zero only when the page structure has changed enough to break
parsing, so the scheduled workflow goes red and notifies the maintainer.

Transient network failures are retried and then skipped (exit 0) so a
snow-forecast.com outage does not raise a false alarm. No third-party deps:
it uses urllib and imports the pure parser directly.
"""

from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Import the pure parser without pulling in Home Assistant: load helpers.py as a
# top-level module rather than the custom_components.ski_resort package (whose
# __init__ imports HA).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components" / "ski_resort"))
from helpers import parse_snow_forecast  # noqa: E402

# Glaciers that ski — and report a base — year-round, so there is always a real
# report to parse regardless of season. Tried in order.
RESORTS = ("Hintertux", "Solden")
USER_AGENT = (
    "home-assistant-ski_resort-canary (https://github.com/yieldhog/ski-resort-ha)"
)


def _fetch(slug: str) -> str:
    url = f"https://www.snow-forecast.com/resorts/{slug}/6day/top"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed https host)
        return resp.read().decode("utf-8", "replace")


def main() -> int:
    last_error: Exception | None = None
    for slug in RESORTS:
        html = None
        for _ in range(2):  # one retry on a transient network error
            try:
                html = _fetch(slug)
                break
            except (urllib.error.URLError, TimeoutError, ValueError) as err:
                last_error = err
                time.sleep(5)
        if html is None:
            continue  # couldn't reach this resort; try the next
        if "snow-depths-table__table" not in html:
            print(f"BREAK: snow-depths table markup not found for {slug}.")
            return 1
        parsed = parse_snow_forecast(html)
        if all(value is None for value in parsed.values()):
            print(f"BREAK: parser extracted nothing for {slug} -> layout changed?")
            return 1
        print(f"OK: {slug} still parses -> {parsed}")
        return 0

    print(f"SKIP: snow-forecast.com unreachable ({last_error}); not a parser break.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
