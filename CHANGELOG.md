# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org/).

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
