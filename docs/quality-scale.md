# Quality scale status & path to Gold

Home Assistant's [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
(Bronze → Silver → Gold → Platinum) is the "gold status" bar. This custom
integration isn't scored by HA core, but we hold it to the same checklist. Status
below reflects the current code.

## Bronze — ✅ complete
- **config-flow** — UI setup via OpenSkiMap search.
- **config-flow-test-coverage** — config flow held to **100%** in CI.
- **unique-config-entry** — entries keyed by OpenSkiMap id; duplicates abort.
- **entity-unique-id** — every entity has `entry_id`-scoped unique ids.
- **has-entity-name** — all entities use `_attr_has_entity_name`.
- **runtime-data** — typed `SkiResortConfigEntry = ConfigEntry[Coordinator]` in
  `entry.runtime_data`.
- **appropriate-polling** — default 180 min, 60 min minimum.
- **common-modules** — `coordinator.py` / `entity.py` / `data.py` split.
- **dependency-transparency** — no third-party requirements; uses HA's shared
  httpx client.
- **config-entry-unloading** — platforms unload cleanly.
- **test-before-configure** — n/a: setup needs no credentials or connection
  (search is offline; weather is keyless).
- **action-setup / entity-event-setup / reauthentication-flow** — n/a (no
  services, no push, no auth).

## Silver — ✅ complete
- **entity-unavailable** — entities expose `available`; optional sources go
  unavailable rather than reporting stale/zero values.
- **log-when-unavailable** — the coordinator logs section failures; HA's
  `DataUpdateCoordinator` logs unavailability once.
- **parallel-updates** — `PARALLEL_UPDATES = 0` on every platform (all reads go
  through the single coordinator).
- **integration-owner** — `codeowners` set in the manifest.
- **test-coverage** — **>95%** enforced in CI (currently ~99%).
- **reauthentication-flow / action-exceptions** — n/a.

## Gold — 🟡 mostly done
Done:
- **devices** — one HA device per ski area, with location, region, and an
  OpenSkiMap `configuration_url`.
- **diagnostics** — redacted entry + coordinator dump.
- **entity-category** — the Resort information sensor is `diagnostic`.
- **entity-device-class** — temperature, wind speed, date, and running classes
  where applicable.
- **entity-translations** — `strings.json` + `translations/en.json`.
- **icon-translations** — `icons.json` for every entity and state.
- **reconfiguration** — the options flow reconfigures units, interval, and all
  provider settings without re-adding.
- **dynamic-devices / stale-devices / discovery** — n/a (one user-added device
  per entry; no network discovery).

Remaining for full Gold:
- [ ] **brands** — submit `ski_resort` icon/logo to
  [home-assistant/brands](https://github.com/home-assistant/brands) (external
  PR; also clears the HACS `brands` check).
- [ ] **exception-translations** — move user-facing error strings into
  `strings.json` under `exceptions`.
- [ ] **entity-disabled-by-default** — review niche entities (e.g. freezing
  level, reported-snow) and disable-by-default where appropriate.
- [ ] **docs-*** — expand docs: data-update cadence, known limitations,
  supported functions, troubleshooting, and dashboard examples (this repo's
  README + this file cover most; split out the remaining sections).

## Platinum — 🟡 partial
- **async-dependency / inject-websession** — ✅ fully async; uses HA's shared
  httpx client.
- **strict-typing** — code is typed throughout; not yet verified under
  `mypy --strict`.

## Summary
The integration is **Silver-complete and substantially Gold**, with a short,
mostly-documentation path to full Gold (plus the external brands submission).
Publishing to HACS additionally requires making the repo public and adding a
description + topics (see the README).
