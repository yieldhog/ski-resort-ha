# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org/).

## [1.2.0] - 2026-08-30

Richer NWS weather alerts.

### Added
- **Weather alert sensor** — a companion text sensor whose state is the most
  significant active NWS alert's event name (e.g. `Flood Watch`), or `None` when
  clear, so a dashboard shows *what* the alert is rather than the binary
  sensor's device-class `Unsafe`. The binary sensor is now named *Weather alert
  active* to distinguish the two.
- **Full alert detail** — both alert entities now expose the alert's
  `description` and `instruction` narrative plus `certainty`, `sender`, and
  `message_type` (in addition to the existing headline / severity / urgency /
  area / onset / expires). When several alerts are active they are sorted
  most-significant first (by severity, then urgency), and the per-alert `alerts`
  list is kept compact (no long text) so the state stays within Home
  Assistant's recorder size limit.

## [1.1.0] - 2026-08-23

New optional data sources and correctness fixes.

### Added
- **5-day snow-forecast sensor** — total upcoming snowfall, with a per-day
  breakdown in the `daily` attribute (from Open-Meteo; no new fetch).
- **"Feels like" sensor** — Open-Meteo apparent temperature (wind chill +
  humidity + sun); the weather entity also gains current and daily-forecast
  apparent temperature.
- **NWS weather alerts** (opt-in, US, keyless) — a *Weather alert* binary
  sensor for active National Weather Service alerts at the resort, with
  headline / severity / expiry (and the full alert list) as attributes.
- **Avalanche danger** (opt-in, keyless) — an *Avalanche danger* enum sensor
  with the danger rating for the resort's forecast zone, plus zone, travel
  advice, expiry, and forecast link as attributes. The source is chosen by the
  resort's country: **avalanche.org** (US) or **Avalanche Canada** (CA). Resorts
  with no coverage latch off so the region layers aren't re-fetched.
- **Throttled RapidAPI snow** — the metered snow-forecast source now refreshes
  on its own slower cadence (`forecast_interval_hours`, default 12 h) so a
  bring-your-own key stays within free-tier quotas; the last reading is kept
  between refreshes.

### Fixed
- **Fresh snow / Powder day** — the 24 h window and the snow-depth / freezing-
  level readings now align to the resort's current local hour instead of
  midnight (Open-Meteo hourly arrays start at 00:00 local).
- **Enrichment retry** — a transient Wikidata/skimap failure no longer
  permanently suppresses the trail-map entity; it retries, and the entity is
  gated on the static skimap id so it appears once the URL resolves.
- Clamp lifts %-open to 100; use the `CONF_FORECAST_RESORT` constant instead of
  a string literal; move the webcam icon to the `image` platform.

## [1.0.1] - 2026-08-22

Quality-scale polish (no functional change):

- **Gold `exception-translations`** — the "added by an older version" setup
  error is now a translated message (`strings.json` → `exceptions`).
- **Platinum `strict-typing`** — the integration passes `mypy --strict`
  (config in `pyproject.toml`), now enforced as a CI step.
- **Gold `docs-*`** — README gains Data updates, Known limitations,
  Troubleshooting (incl. the Liftie base-URL gotcha), an example dashboard
  card, and removal instructions.
- Documented `entity-disabled-by-default` as a deliberate opt-out (all entities
  ship enabled).

## [1.0.0] - 2026-08-22

**First stable release.** Graduates the 0.6.0 beta series to 1.0.0 — no
functional change from `0.6.0b8`, just the move out of pre-release. Highlights:

- **Keyless by default:** search ~6,000 OpenSkiMap ski areas; weather + snow from
  free Open-Meteo; offline terrain metadata (lifts by type, runs by difficulty,
  vertical, elevations).
- **Free live lift status** via a self-hosted [Liftie](https://github.com/pirxpilot/liftie)
  instance — see the companion
  [add-on](https://github.com/yieldhog/hass-liftie-addon) — or optional RapidAPI
  skiapi; percentage open computed against OpenSkiMap's authoritative lift count.
- **Optional extras:** RapidAPI snow-forecast, a skimap.org trail-map image, a
  resort webcam (image entity, OpenSnow auto-convert), and powder-day /
  resort-open binary sensors.
- **Hardened:** every optional source degrades independently; nothing can crash
  the keyless core. The Liftie base URL tolerates a pasted full API path.
- **Bundled brand icon** (`brand/icon.png` + `icon@2x.png`) so the integration
  shows its own icon in Home Assistant (2026.3.0+ serves local brand images
  directly — no home-assistant/brands submission needed).

## [0.6.0b8] - 2026-08-22

- **Liftie base URL is now forgiving of a pasted full API URL.** Entering the
  whole endpoint (`http://host:3000/api/resort/vail`) instead of just the server
  root previously produced a doubled path (`.../api/resort/vail/api/resort/vail`)
  and a 404, leaving the lift sensors unavailable. The client now trims any
  `/api/...` suffix back to the root. The options field description was also
  clarified to ask for the host and port only.

## [0.6.0b7] - 2026-08-21

- **Webcam is now an `image` entity, not a `camera` — the live preview works.**
  A still camera's live view is an MJPEG stream that browsers only render for
  JPEG frames, which made WebP webcams (e.g. OpenSnow) show a broken preview
  even though snapshots downloaded fine. An **image** entity renders as a plain
  `<img>`, which displays WebP/PNG/JPEG natively — no MJPEG, no transcoding, no
  Pillow dependency. The entity moves from `camera.<name>_webcam` to
  `image.<name>_webcam` and refreshes each poll. Clearing the URL still removes
  it. **Note:** after updating, delete the old, now-unavailable
  `camera.*_webcam` entity once (Settings → Devices & Services → Entities).

## [0.6.0b6] - 2026-08-21

- **Stop retrying on HTTP 429 (rate/quota limit).** RapidAPI's metered plans
  return `429` once you hit your allowance; retrying that 3× per poll only
  burned more of the quota and could never succeed. `429` now fails fast with a
  clear "rate or quota limit reached" message, and the affected source degrades
  to unavailable for that cycle. Transient server errors (`500/502/503/504`)
  are still retried.

## [0.6.0b5] - 2026-08-21

- **Webcam live view: set the stream content-type correctly and warn on
  transcode failure.** HA reads `Camera.content_type` (a plain attribute) for
  the MJPEG live-view header; the previous fix set `_attr_content_type`, which
  HA's camera doesn't read. Now the correct attribute is set to `image/jpeg`
  (frames are always transcoded to JPEG). If a frame ever can't be transcoded,
  a warning is logged naming the URL and content-type, so a broken preview is
  diagnosable from the log instead of silent.

## [0.6.0b4] - 2026-08-21

- **Clearing an optional field in the options now actually clears it.** The
  options form pre-filled each optional text field (webcam URL, Liftie URL,
  RapidAPI key, forecast resort, lift slug) with a `default`, which Home
  Assistant silently re-injected when you emptied the field — so blanking the
  webcam URL never removed the webcam (the b3 removal logic never saw an empty
  value). These now use `suggested_value`, so a cleared field stays cleared and
  the webcam (or any other optional setting) is removed on save.

## [0.6.0b3] - 2026-08-21

- **Clearing the webcam URL now removes the camera entity.** Previously,
  blanking the webcam URL in the options left the `camera.*_webcam` entity
  behind as `unavailable`. The camera platform now deletes the entity from the
  registry when no URL is configured, so removing a webcam actually removes it.

## [0.6.0b2] - 2026-08-21

- **Fixed the webcam live view showing a broken image.** Home Assistant renders
  a still-camera's live preview as an MJPEG stream, and browsers only decode
  **JPEG** frames inside it — so WebP webcams (e.g. OpenSnow's `.webp` frames)
  appeared broken in the more-info view even though "Download snapshot" saved a
  correct picture. The camera now transcodes any non-JPEG frame to JPEG (off the
  event loop) before serving it, so the live preview works. Uses Pillow, which
  ships with Home Assistant; if it were ever unavailable the original bytes are
  served unchanged.

## [0.6.0b1] - 2026-08-21

**First public beta.** Consolidates everything below into the first tagged
release: OpenSkiMap-anchored setup (search ~6,000 ski areas, no API key), free
Open-Meteo weather + snow, offline terrain metadata (lifts by type, runs by
difficulty, vertical, elevations), an optional live lift source (self-hosted
Liftie or RapidAPI skiapi), an optional RapidAPI snow-forecast, a skimap.org
trail-map image, a resort-information sensor, powder-day / resort-open binary
sensors, and an optional webcam camera (manual URL, with OpenSnow auto-convert).
Hardened error handling throughout; nothing optional can crash the keyless core.

## [0.5.2] - 2026-08-21

- **Removed the Wikidata resort-photo image entity.** It added little (the
  Wikidata photo is often generic or mismatched). The **trail map** image entity
  stays, and Wikidata's website + opening year still appear on the Resort
  information sensor. Existing installs will show the old `image.*_resort_photo`
  as unavailable — delete it from the entity registry.

## [0.5.1] - 2026-08-21

- **OpenSnow cams made easy.** The webcam option now accepts an OpenSnow cam
  *page* URL (e.g. `opensnow.com/location/vail/cams/3380`) and converts it
  automatically to the direct latest-frame image
  (`cams.opensnow.com/latest/3380/720.webp`) — which serves cleanly over HTTP
  and updates in place. Direct image URLs still work unchanged.

## [0.5.0] - 2026-08-21

- **Webcam camera (optional).** Add a resort webcam by pasting a direct
  still-image URL in the options — it appears as a `camera` entity on the resort
  device. Fetches follow redirects and swallow errors (a broken URL never
  raises), a short cache keeps polling gentle, and the last good frame is served
  if a refresh fails. The URL is validated up front. Fully optional and
  independent of the polled data.

## [0.4.2] - 2026-08-21

Error-handling hardening pass.

- **Optional sources never blank the integration.** The coordinator now
  degrades the *whole* `SkiResortError` hierarchy — including auth errors from a
  bad RapidAPI key — so a rejected key or a failing optional source disables
  just that section, never the keyless core.
- **Malformed-URL safety.** `httpx.InvalidURL` (e.g. a Liftie base URL missing
  its scheme) is caught and degraded instead of crashing; the options flow also
  validates the URL up front.
- **Enrichment can't crash a refresh.** A bad Wikidata date (`ValueError`) is
  now caught; enrichment stays best-effort.
- **Resort photo actually loads.** The image entity follows redirects (the
  Wikidata/Commons URL is a 302) and swallows fetch errors.
- **Concurrent fetches.** Weather, snow, lifts, and enrichment run in parallel,
  so one slow source can't hold up or blank the others.
- **Clear message for legacy entries** (missing the OpenSkiMap snapshot) and a
  guard if a chosen ski area is no longer in the bundled index.

## [0.4.1] - 2026-08-21

- Fix hassfest: remove a literal URL from the `liftie_base_url` option
  description (hassfest disallows URLs in translation strings).

## [0.4.0] - 2026-08-21

Open-data enrichment (Tier 3) and a quality-scale pass.

- **Resort photo** and **trail map** image entities — from Wikidata (Wikimedia
  Commons) and skimap.org respectively, resolved once and served as HA `image`
  entities (only when available).
- **Resort information** diagnostic sensor — operating status plus region,
  website, opening year (Wikidata), coordinates, and OpenSkiMap/Wikidata/skimap
  links.
- Bundled index now carries the skimap.org id; enrichment is best-effort and
  never blocks setup.
- Quality scale: `PARALLEL_UPDATES = 0` on all platforms, a diagnostic entity
  category, and a documented path to Gold (`docs/quality-scale.md`). The
  integration is Silver-complete and substantially Gold.

## [0.3.0] - 2026-08-21

Re-anchored the integration on OpenSkiMap and open data. **Breaking:** the
config model changed from a RapidAPI resort name to an OpenSkiMap ski area;
re-add resorts after upgrading.

- **OpenSkiMap search flow** — pick from ~6,000 bundled ski areas by name (+
  country filter); resorts are keyed by their canonical OpenSkiMap id. No API
  key required.
- **Free weather** — a per-resort `weather` entity plus fresh-snow (24h), snow
  depth, freezing level, temperature, and wind sensors, all from **Open-Meteo**
  (keyless) at the resort's coordinates.
- **Terrain metadata** (offline, from OpenSkiMap) — lifts (by type), runs (by
  difficulty), vertical drop, summit/base elevation, snowmaking.
- **Optional live lift status** — self-hosted **Liftie** or RapidAPI skiapi,
  with the Liftie slug **auto-mapped** from a bundled crosswalk; *% open* uses
  OpenSkiMap's authoritative lift total.
- **Optional RapidAPI snow-forecast** — reported base/summit depth, fresh snow,
  last snowfall date.
- Bundled OpenSkiMap index + Liftie crosswalk with a regeneration script;
  data-source attributions (ODbL/CC-BY/BSD) included.

## [0.1.0] - 2026-08-21

Initial release.

- Config flow: RapidAPI key + resort name, validated by a live snow-conditions
  fetch; one config entry per resort; reauth flow for a rotated key.
- Snow sensors: fresh snowfall, top snow depth (with up/down/stable trend vs the
  previous poll), base snow depth, last snowfall date.
- Forecast sensor: 3-day summary with the full 5-day payload and resort metadata
  exposed as attributes.
- Optional lift status (gated by an options toggle → Ski Resorts and Conditions
  API): lifts open, total, and percentage open, plus a "Resort open" binary
  sensor.
- "Powder day" binary sensor (fresh snowfall > 0).
- Options: poll interval, units (imperial/metric), forecast elevation, lift
  toggle and slug.
- Resilient API client (retry/backoff, concurrency cap) and per-section
  graceful degradation in the coordinator; diagnostics with the key redacted.
