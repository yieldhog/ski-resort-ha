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

## Gold — ✅ complete
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
- **brands** — the brand icon is **bundled** in `custom_components/ski_resort/
  brand/` (HA 2026.3.0+ serves local brand images directly; no
  home-assistant/brands submission needed). The HACS action still checks the
  brands CDN, so its `brands` check stays ignored in CI.
- **exception-translations** — the setup `ConfigEntryError` uses a
  `translation_key` with a message under `strings.json` → `exceptions`.
- **docs-*** — README covers installation, configuration parameters, data
  updates, known limitations, troubleshooting, a dashboard example, and removal.
- **dynamic-devices / stale-devices / discovery** — n/a (one user-added device
  per entry; no network discovery).

Deliberately skipped:
- **entity-disabled-by-default** — all entities ship **enabled**. The niche
  ones (freezing level, reported-snow) were considered for disable-by-default,
  but we prefer not to hide data users may expect; they can disable any entity
  per-entity in HA.

## Platinum — 🟡 partial
- **async-dependency / inject-websession** — ✅ fully async; uses HA's shared
  httpx client.
- **strict-typing** — ✅ passes `mypy` in **strict** mode (config in
  `pyproject.toml`), enforced in CI.

## Summary
The integration is **Silver- and Gold-complete** (with `entity-disabled-by-
default` a deliberate opt-out), and meets the Platinum typing bar. It is
distributed as a HACS custom repository with a bundled brand icon.
