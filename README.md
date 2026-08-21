# Ski Resort — Home Assistant integration

[![hacs][hacs-badge]][hacs]
![HA Version](https://img.shields.io/badge/Home%20Assistant-%3E%3D%202024.12-brightgreen)

A native Home Assistant integration for the world's ski resorts, anchored on
**[OpenSkiMap](https://openskimap.org)** — the open, OpenStreetMap-derived ski
database. Search **~6,000 ski areas**, add one as a device, and get a real
**weather entity**, **snow forecast**, **terrain metadata**, and optional **live
lift status** — **no API key required** to get started.

Everything is polled locally and exposed as first-class HA entities, so you can
build dashboards and automations ("Vail powder day tomorrow", "the mountain just
opened") from open data.

> **Unofficial.** Not affiliated with any resort. It combines open data from
> OpenSkiMap (OpenStreetMap + Skimap.org), Open-Meteo, and Liftie.

---

## Highlights

- **Search by name, no key needed.** Setup searches a bundled OpenSkiMap index
  (~6,000 downhill areas); pick your resort and you're done. Weather comes from
  the free **Open-Meteo** service — no account, no key.
- **A real weather entity per resort** — current conditions + a 7-day forecast,
  from Open-Meteo at the resort's exact coordinates.
- **Snow sensors** — fresh snowfall (next 24h), snow depth, freezing level, plus
  temperature and wind.
- **Terrain metadata** (from OpenSkiMap, offline) — lift count (by type), run
  count (**by difficulty**), vertical drop, summit & base elevation, snowmaking.
- **Live lift status (optional)** — *Lifts open*, *% open* (against OpenSkiMap's
  authoritative total), and a *Resort open* binary sensor, from a **self-hosted
  [Liftie](https://github.com/pirxpilot/liftie)** instance or the RapidAPI
  *ski-resorts-and-conditions* product. The Liftie slug is **auto-mapped** from
  your chosen ski area.
- **Powder day** binary sensor.
- **Trail map** (open data) — the skimap.org trail map as an HA image entity,
  plus a resort-info diagnostic sensor with links and facts.
- **Canonical IDs.** Every resort is keyed by its OpenSkiMap id, so entities are
  stable and consistent with the wider open-ski-data ecosystem.

## Data sources & licenses

| Source | Used for | License |
| --- | --- | --- |
| [OpenSkiMap](https://openskimap.org) (OpenStreetMap + Skimap.org) | Resort identity, geography, terrain metadata | **ODbL** |
| [Open-Meteo](https://open-meteo.com) | Weather + snow forecast | **CC-BY 4.0** |
| [Liftie](https://github.com/pirxpilot/liftie) | Live lift status (self-hosted) | **BSD-3** |
| RapidAPI *ski-resorts-and-conditions* / *ski-resort-forecast* | Optional lift status / snow-forecast | proprietary |

The bundled index and Liftie crosswalk are derived data under ODbL/BSD; see
[`custom_components/ski_resort/data/NOTICE.md`](custom_components/ski_resort/data/NOTICE.md).

## Installation

### HACS

1. Add this repository as a **custom repository** (category: *Integration*):
   `https://github.com/yieldhog/ski-resort-ha`.
2. Install **Ski Resort** and restart Home Assistant.

### Manual

Copy `custom_components/ski_resort` into `config/custom_components/` and restart.

## Setup

**Settings → Devices & Services → Add Integration → Ski Resort.**

1. **Search** for your resort by name (optionally filter by country).
2. **Pick** the matching OpenSkiMap ski area.

That's it — the weather entity, snow sensors, and terrain sensors appear with no
key. The Liftie slug is filled in automatically when known.

### Options

**Configure** on the integration exposes:

- **Update interval** and **units** (imperial/metric).
- **Lift slug** — auto-filled; override if the auto-map missed.
- **Self-hosted Liftie base URL** (e.g. `http://homeassistant.local:3000`) — if
  set, lift status comes from your free Liftie instance.
- **RapidAPI key** — enables skiapi lift status and the RapidAPI snow-forecast.
- **RapidAPI snow-forecast resort name** — adds reported base/summit depth etc.
- **Webcam image URL** — a direct still-image link to a resort webcam, shown as a `camera` entity. You can also paste an **OpenSnow cam page URL** (`opensnow.com/location/.../cams/ID`) and it's converted automatically. Some resorts block hotlinking.

> **Lift status is optional.** liftie.info's public API is Cloudflare-protected
> against server-side calls, so live lifts need either a **self-hosted Liftie**
> or a **RapidAPI key** (skiapi is the same Liftie data). Everything else works
> without either.

## Entities

| Entity | Platform | Source |
| --- | --- | --- |
| Weather (current + daily forecast) | weather | Open-Meteo |
| Fresh snowfall (24h) · Snow depth · Freezing level · Temperature · Wind | sensor | Open-Meteo |
| Lifts · Runs · Vertical drop · Summit / Base elevation | sensor | OpenSkiMap |
| Lifts open · % open | sensor | Liftie/skiapi (optional) |
| Reported summit/base depth · fresh snow · last snowfall date | sensor | RapidAPI (optional) |
| Resort information (status + links/facts) | sensor (diagnostic) | OpenSkiMap + Wikidata |
| Trail map | image | skimap.org |
| Webcam | camera | your resort webcam URL (optional) |
| Powder day | binary_sensor | Open-Meteo |
| Resort open | binary_sensor | Liftie/skiapi (optional) |

## Quality scale

The integration is held to Home Assistant's Integration Quality Scale — it is
Silver-complete and substantially Gold. See
[`docs/quality-scale.md`](docs/quality-scale.md) for the full checklist and the
remaining path to Gold.

## Refreshing the bundled data

The OpenSkiMap index and Liftie crosswalk are regenerated by a script (run it
periodically to pick up new resorts):

```bash
python3 scripts/build_ski_area_index.py /path/to/liftie/checkout
```

## Development

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/python -m pytest -q
```

CI runs **hassfest**, the **HACS** action, **ruff**, and pytest with coverage.

## License

Integration code: [MIT](LICENSE). Bundled data retains its upstream licenses
(see above).

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
