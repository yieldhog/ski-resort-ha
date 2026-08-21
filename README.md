# Ski Resort Forecast — Home Assistant integration

[![hacs][hacs-badge]][hacs]
![HA Version](https://img.shields.io/badge/Home%20Assistant-%3E%3D%202024.12-brightgreen)

A native Home Assistant integration for mountain **ski-resort snow conditions,
forecasts, and lift status**. It polls the RapidAPI *Ski Resort Forecast* API and
exposes each resort as a first-class HA **device** with sensors — fresh snowfall,
snow depth (top & base, with a trend), the last snowfall date, and a 3-/5-day
forecast — plus optional live **lift status** from the *Ski Resorts and
Conditions* API.

Everything is polled directly and exposed locally, so you can build dashboards
and automations ("Vail got fresh snow overnight", "the mountain just opened")
without any REST-sensor YAML or template gymnastics.

> **Unofficial.** Not affiliated with any resort or with RapidAPI. It wraps the
> third-party [Ski Resort Forecast][forecast-api] and
> [Ski Resorts and Conditions][conditions-api] APIs.

---

## Features

- **One device per resort.** Add as many resorts as you like — run the setup
  flow once per resort; each becomes its own device with grouped entities.
- **Snow sensors** — *Fresh snowfall*, *Top snow depth* (with an `up`/`down`/
  `stable` **trend** and numeric `change` attribute computed live from the last
  poll, no database), *Base snow depth*, and *Last snowfall date*
  (`device_class: date`).
- **Forecast sensor** — a *3-day forecast* summary as state, with the full
  `summary_5day`, `forecast_5day`, and resort metadata (region, elevations,
  coordinates) carried as attributes for cards and automations.
- **Optional lift status** — *Lifts open*, *Lifts total*, *Lifts open
  percentage*, and a *Resort open* binary sensor, from the second API. Gated by
  an options toggle so you only spend an API call when you want it.
- **Powder day** binary sensor — on whenever fresh snowfall is greater than zero.
- **Imperial or metric**, a configurable **poll interval**, and a **forecast
  elevation** (top/mid/base) — all in the UI options.
- **Robust by design** — retry-with-backoff and a concurrency cap in the API
  client, and per-section graceful degradation so one flaky endpoint never
  blanks the whole resort. Reauth flow for a rotated key; diagnostics with the
  API key redacted.

## Requirements

A [RapidAPI](https://rapidapi.com/) account and key subscribed to:

- **[Ski Resort Forecast][forecast-api]** — required (snow + forecast).
- **[Ski Resorts and Conditions][conditions-api]** — optional, only if you turn
  on lift status. The same RapidAPI key works for both.

## Installation

### HACS (recommended)

1. In HACS, add this repository as a **custom repository** (category:
   *Integration*): `https://github.com/yieldhog/ski-resort-ha`.
2. Install **Ski Resort Forecast** and restart Home Assistant.

### Manual

Copy `custom_components/ski_resort` into your Home Assistant `config/custom_components/`
directory and restart.

## Setup

**Settings → Devices & Services → Add Integration → Ski Resort Forecast.**

| Field | Notes |
| --- | --- |
| RapidAPI key | Your key, subscribed to the Ski Resort Forecast API. |
| Resort name | As the forecast API spells it — hyphens for spaces (e.g. `Vail`, `Beaver-Creek`, `Val-dIsere`). |
| Display name | Optional friendly name for the device. |
| Units | Imperial (in) or metric (cm). |

The key and resort are validated with a live snow-conditions request before the
entry is created, so a typo or an unsubscribed key is caught immediately.

### Options

**Configure** on the integration exposes: update interval (minutes), units,
forecast elevation (top/mid/base), **Enable lift status** (+ the skiapi resort
*slug*, e.g. `vail`). Changing options reloads the resort automatically.

## Entities

| Entity | Platform | Notes |
| --- | --- | --- |
| Fresh snowfall | sensor | `measurement`, in/cm |
| Top snow depth | sensor | `measurement`; `trend` + `change` attributes |
| Base snow depth | sensor | `measurement` |
| Last snowfall date | sensor | `device_class: date` |
| 3-day forecast | sensor | summary text; 5-day + metadata as attributes |
| Lifts open / total / open % | sensor | only when lift status is enabled |
| Powder day | binary_sensor | on when fresh snowfall > 0 |
| Resort open | binary_sensor | on when ≥ 1 lift open (lift status enabled) |

## Development

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/python -m pytest -q
```

CI (`.github/workflows/validate.yml`) runs **hassfest**, the **HACS** action,
**ruff**, and pytest with coverage on every push and PR.

## License

[MIT](LICENSE).

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[forecast-api]: https://rapidapi.com/joeykyber/api/ski-resort-forecast
[conditions-api]: https://rapidapi.com/random-shapes-random-shapes-default/api/ski-resorts-and-conditions
