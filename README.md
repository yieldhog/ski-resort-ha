# Ski Resort — Home Assistant integration

[![hacs][hacs-badge]][hacs]
[![GitHub Release][release-badge]][releases]
[![Hassfest][hassfest-badge]][hassfest-workflow]
[![Tests][tests-badge]][tests-workflow]
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
| [NWS](https://www.weather.gov/documentation/services-web-api) (api.weather.gov) | Weather alerts (US, optional) | **US public domain** |
| [avalanche.org](https://github.com/NationalAvalancheCenter/Avalanche.org-Public-API-Docs) | Avalanche danger rating (US, optional) | free (gov/nonprofit) |
| [Avalanche Canada](https://avalanche.ca) | Avalanche danger rating (Canada, optional) | free |
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
- **NWS weather alerts (US)** — opt-in; adds a *Weather alert* binary sensor
  (with the alert headline/severity/expiry as attributes) from the free NWS API.
- **Avalanche danger (US & Canada)** — opt-in; adds an *Avalanche danger*
  sensor with the danger rating for the resort's forecast zone (level, zone,
  travel advice, expiry, and forecast link as attributes). Keyless. The source
  is chosen by the resort's country — **avalanche.org** in the US, **Avalanche
  Canada** in Canada. Europe isn't covered yet; resorts outside a forecast zone
  won't report.
- **Lift slug** — auto-filled; override if the auto-map missed.
- **Self-hosted Liftie base URL** — the **host and port only** (e.g.
  `http://homeassistant.local:3000`), **not** the `/api/resort/...` path. If set,
  lift status comes from your free Liftie instance. See
  [Self-hosted lift status](#self-hosted-lift-status-free) below.
- **RapidAPI key** — enables the RapidAPI snow-forecast, and skiapi lift status
  only as a fallback. **A self-hosted Liftie URL always wins for lifts** — with
  both set, lifts come from Liftie and the key is used solely for the
  snow-forecast (no RapidAPI quota spent on lifts). The `lifts_open` sensor's
  `source` attribute (`liftie`/`skiapi`) shows which is in use.
- **RapidAPI snow-forecast resort name** — adds reported base/summit depth etc.
- **RapidAPI snow refresh interval (hours)** — polls the metered snow-forecast
  source on its own slow cadence (default **12h**, independent of the main
  update interval) so a bring-your-own key stays inside free-tier quotas;
  the last reading is kept between refreshes.
- **Webcam image URL** — a direct still-image link to a resort webcam, shown as an `image` entity. You can also paste an **OpenSnow cam page URL** (`opensnow.com/location/.../cams/ID`) and it's converted automatically. Some resorts block hotlinking.

> **Lift status is optional.** liftie.info's public API is Cloudflare-protected
> against server-side calls, so live lifts need either a **self-hosted Liftie**
> or a **RapidAPI key** (skiapi is the same Liftie data). Everything else works
> without either.

## Self-hosted lift status (free)

For live lift open/closed counts with **no API key and no request quota**, run
[Liftie](https://github.com/pirxpilot/liftie) on your own network. The easiest
way is the companion Home Assistant add-on:

**[yieldhog/hass-liftie-addon](https://github.com/yieldhog/hass-liftie-addon)**

1. In Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**,
   add `https://github.com/yieldhog/hass-liftie-addon`, then install and start
   **Liftie**. (Add-ons require Home Assistant OS or Supervised.)
2. In this integration's **Configure**:
   - **Liftie base URL** → the add-on's host and port, e.g.
     `http://homeassistant.local:3000` (or your host's IP) — **not** the
     `/api/resort/...` path.
   - **Lift slug** → your resort (e.g. `vail`); usually auto-filled.
3. Leave the **RapidAPI key** blank — when a Liftie base URL is set, it wins.

The add-on lets you limit which resorts it tracks, tune scrape frequency, and it
opens an automatic PR when upstream Liftie updates. See its
[docs](https://github.com/yieldhog/hass-liftie-addon/blob/main/liftie/DOCS.md).

## Entities

| Entity | Platform | Source |
| --- | --- | --- |
| Weather (current + daily forecast) | weather | Open-Meteo |
| Fresh snowfall (24h) · Snow depth · Freezing level · Temperature · Wind | sensor | Open-Meteo |
| Snow forecast (5-day total; per-day snowfall in the `daily` attribute) | sensor | Open-Meteo |
| Lifts · Runs · Vertical drop · Summit / Base elevation | sensor | OpenSkiMap |
| Lifts open · % open | sensor | Liftie/skiapi (optional) |
| Reported summit/base depth · fresh snow · last snowfall date | sensor | RapidAPI (optional) |
| Resort information (status + links/facts) | sensor (diagnostic) | OpenSkiMap + Wikidata |
| Trail map | image | skimap.org |
| Webcam | image | your resort webcam URL (optional) |
| Avalanche danger (rating + zone/advice/expiry) | sensor | avalanche.org / Avalanche Canada (optional, US & CA) |
| Powder day | binary_sensor | Open-Meteo |
| Resort open | binary_sensor | Liftie/skiapi (optional) |
| Weather alert (active NWS alert + headline) | binary_sensor | NWS (optional, US) |

## Data updates

The integration **polls** on a fixed interval (default **3 hours**, minimum 60
minutes — set it under **Configure**). Weather/snow come from Open-Meteo; live
lift status from Liftie/skiapi when configured; terrain metadata is bundled and
never fetched. Each source updates independently — if one is down, the others
still refresh. Static enrichment (trail map, website, opening year) is fetched
once and cached.

## Known limitations

- **Lift status needs a source.** liftie.info's public API blocks server-side
  calls, so live lifts require a self-hosted Liftie or a RapidAPI key. Without
  either, the lift/resort-open entities are simply absent.
- **Off-season shows 0 open.** Correctly reflects reality — Liftie reports lifts
  as `scheduled`/`closed` outside the season.
- **Lift total vs. open source.** The lift *total* comes from OpenSkiMap
  (authoritative); *open* count comes from Liftie, so the two can occasionally
  disagree (e.g. a resort adds a lift OpenSkiMap hasn't mapped yet).
- **RapidAPI is metered.** The optional RapidAPI sources have request quotas;
  the self-hosted Liftie add-on avoids this entirely.
- **Bundled resort index.** Search covers the resorts in the bundled OpenSkiMap
  snapshot; regenerate it (below) to pick up newly added areas.

## Troubleshooting

- **Lift sensors are `unavailable`.** Check two things under **Configure**:
  (1) the **Lift slug** is set (e.g. `vail`), and (2) the **Liftie base URL** is
  the **host and port only** (e.g. `http://homeassistant.local:3000`) — a full
  `.../api/resort/<slug>` URL produces a doubled path and a 404. Then look at
  **Settings → System → Logs** for a `ski_resort` line naming the cause.
- **Weather is missing.** Open-Meteo is keyless and global; a transient failure
  clears on the next poll. Persistent failure usually means outbound HTTPS is
  blocked on the HA host.
- **RapidAPI source `unavailable`.** The log will say `rate or quota limit
  reached (429)` when the plan's quota is spent — switch to the self-hosted
  Liftie add-on, or wait for the quota to reset.
- **Webcam not showing.** Confirm the URL returns an image directly (some
  resorts block hotlinking). OpenSnow cam *page* URLs are auto-converted.

## Example dashboard card

```yaml
type: entities
title: Vail
entities:
  - entity: weather.vail_weather
  - entity: sensor.vail_fresh_snowfall_24h
  - entity: sensor.vail_snow_depth
  - entity: sensor.vail_snow_forecast_5_day  # state = 5-day total; `daily` attr = per-day
  - entity: sensor.vail_lifts_open
  - entity: binary_sensor.vail_powder_day
  - entity: binary_sensor.vail_resort_open
  - entity: image.vail_trail_map
```

## Removing the integration

**Settings → Devices & Services → Ski Resort → ⋮ → Delete** removes the config
entry and all its entities. Then remove the repository from HACS. (The
self-hosted Liftie add-on, if installed, is uninstalled separately from the
add-on store.)

## Quality scale

The integration is held to Home Assistant's Integration Quality Scale — Bronze,
Silver, and Gold complete, and it meets the Platinum strict-typing bar (`mypy
--strict` in CI). See [`docs/quality-scale.md`](docs/quality-scale.md) for the
full checklist.

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

CI runs **hassfest**, the **HACS** action, **ruff**, **mypy** (strict), and
pytest with coverage.

## License

Integration code: [MIT](LICENSE). Bundled data retains its upstream licenses
(see above).

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[releases]: https://github.com/yieldhog/ski-resort-ha/releases
[release-badge]: https://img.shields.io/github/v/release/yieldhog/ski-resort-ha?display_name=tag&sort=semver
[hassfest-workflow]: https://github.com/yieldhog/ski-resort-ha/actions/workflows/hassfest.yml
[hassfest-badge]: https://github.com/yieldhog/ski-resort-ha/actions/workflows/hassfest.yml/badge.svg
[tests-workflow]: https://github.com/yieldhog/ski-resort-ha/actions/workflows/tests.yml
[tests-badge]: https://github.com/yieldhog/ski-resort-ha/actions/workflows/tests.yml/badge.svg
