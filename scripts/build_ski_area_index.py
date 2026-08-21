#!/usr/bin/env python3
"""Regenerate the bundled OpenSkiMap index and Liftie crosswalk.

Downloads OpenSkiMap's daily ``ski_areas.geojson`` (ODbL; OpenStreetMap
contributors & Skimap.org) and distils it to a slim, gzipped index the config
flow searches offline. Also builds a Liftie↔OpenSkiMap crosswalk from Liftie's
per-resort coordinates (BSD) so a chosen ski area maps to its Liftie/skiapi slug
automatically. Run periodically to refresh:

    python3 scripts/build_ski_area_index.py [path-to-liftie-checkout]

Outputs:
    custom_components/ski_resort/data/ski_area_index.json.gz
    custom_components/ski_resort/data/liftie_crosswalk.json.gz
"""

from __future__ import annotations

import glob
import gzip
import json
import math
import os
import re
import sys
import urllib.request
from pathlib import Path

SKI_AREAS_URL = "https://tiles.openskimap.org/geojson/ski_areas.geojson"
DATA_DIR = Path(__file__).resolve().parents[1] / "custom_components/ski_resort/data"


def _lift_types(props: dict) -> dict[str, int]:
    by_type = (props.get("statistics", {}).get("lifts", {}) or {}).get("byType", {})
    return {
        k: (v.get("count", 0) if isinstance(v, dict) else 0)
        for k, v in (by_type or {}).items()
    }


def _slim(feature: dict) -> dict:
    props = feature["properties"]
    place = (props.get("places") or [{}])[0]
    en = place.get("localized", {}).get("en", {})
    center = (props.get("viewportHint") or {}).get("center")
    stats = props.get("statistics", {}) or {}
    runs = stats.get("runs", {}) or {}
    lift_types = _lift_types(props)
    downhill = (runs.get("byActivity", {}) or {}).get("downhill", {}) or {}
    by_diff: dict[str, int] = {}
    run_km = snow_km = 0.0
    for diff, rec in (downhill.get("byDifficulty") or {}).items():
        if isinstance(rec, dict):
            by_diff[diff] = rec.get("count", 0)
            run_km += rec.get("lengthInKm", 0) or 0
            snow_km += rec.get("snowmakingLengthInKm", 0) or 0
    return {
        "id": props["id"],
        "name": props["name"],
        "country": en.get("country"),
        "region": en.get("region"),
        "cc": place.get("iso3166_1Alpha2"),
        "lat": round(center[1], 5) if center else None,
        "lon": round(center[0], 5) if center else None,
        "status": props.get("status"),
        "lifts": sum(lift_types.values()),
        "liftTypes": lift_types,
        "runs": sum(by_diff.values()),
        "runKm": round(run_km, 1),
        "byDiff": by_diff,
        "snowKm": round(snow_km, 1),
        "vMin": runs.get("minElevation"),
        "vMax": runs.get("maxElevation"),
        "web": (props.get("websites") or [None])[0],
        "wd": props.get("wikidataID"),
        "poly": feature["geometry"]["type"] in ("Polygon", "MultiPolygon"),
        "nordic": "nordic" in (props.get("activities") or []),
    }


def _haversine(a_lat, a_lon, b_lat, b_lon) -> float:
    r = 6371.0
    d_lat = math.radians(b_lat - a_lat)
    d_lon = math.radians(b_lon - a_lon)
    x = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(a_lat))
        * math.cos(math.radians(b_lat))
        * math.sin(d_lon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(x))


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def build_crosswalk(features: list[dict], liftie_dir: str) -> dict:
    """Match each Liftie resort (by coordinates + name) to an OpenSkiMap id."""
    osm = []
    for feature in features:
        props = feature["properties"]
        center = (props.get("viewportHint") or {}).get("center")
        if center and props.get("name"):
            osm.append(
                (props["id"], props["name"], _norm(props["name"]), center[1], center[0])
            )
    crosswalk: dict[str, dict] = {}
    for path in glob.glob(os.path.join(liftie_dir, "lib/resorts/*/resort.json")):
        slug = os.path.basename(os.path.dirname(path))
        with open(path, encoding="utf-8") as handle:
            resort = json.load(handle)
        ll = resort.get("ll")
        if not ll:
            continue
        lname = _norm(resort.get("name"))
        candidates = []
        for area_id, name, name_norm, olat, olon in osm:
            dist = _haversine(ll[1], ll[0], olat, olon)
            name_hit = lname and (lname in name_norm or name_norm in lname)
            if dist <= 3 or (name_hit and dist <= 25):
                score = dist - (5 if name_hit else 0)
                candidates.append((score, dist, area_id, name))
        if candidates:
            candidates.sort()
            _, dist, area_id, name = candidates[0]
            crosswalk[slug] = {"id": area_id, "dist": round(dist, 2), "name": name}
    return crosswalk


def main() -> None:
    liftie_dir = sys.argv[1] if len(sys.argv) > 1 else "/home/user/pirxpilot/liftie"
    with urllib.request.urlopen(SKI_AREAS_URL) as resp:  # noqa: S310
        features = json.load(resp)["features"]

    index = [
        _slim(f)
        for f in features
        if "downhill" in (f["properties"].get("activities") or [])
        and f["properties"].get("name")
    ]
    (DATA_DIR / "ski_area_index.json.gz").write_bytes(
        gzip.compress(json.dumps(index, separators=(",", ":"), ensure_ascii=False).encode())
    )
    print(f"Wrote {len(index)} ski areas.")

    if os.path.isdir(liftie_dir):
        crosswalk = build_crosswalk(features, liftie_dir)
        (DATA_DIR / "liftie_crosswalk.json.gz").write_bytes(
            gzip.compress(json.dumps(crosswalk, separators=(",", ":")).encode())
        )
        print(f"Wrote crosswalk for {len(crosswalk)} Liftie resorts.")
    else:
        print(f"Liftie checkout not found at {liftie_dir}; kept existing crosswalk.")


if __name__ == "__main__":
    main()
