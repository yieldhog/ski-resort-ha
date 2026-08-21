# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org/).

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
