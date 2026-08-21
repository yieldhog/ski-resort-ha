# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org/).

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
