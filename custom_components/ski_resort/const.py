"""Constants for the Ski Resort integration.

The integration is anchored on OpenSkiMap ski-area IDs (the canonical open
identifier). A bundled, distilled OpenSkiMap index supplies each resort's
identity, geography, and terrain metadata offline; weather/snow comes from the
free Open-Meteo API (no key); live lift status is optional (self-hosted Liftie
or the RapidAPI skiapi product, auto-mapped from a bundled Liftie crosswalk).
"""

from __future__ import annotations

DOMAIN = "ski_resort"
MANUFACTURER = "OpenSkiMap"

# --- Hosts -----------------------------------------------------------------
OPEN_METEO_HOST = "api.open-meteo.com"
CONDITIONS_HOST = "ski-resorts-and-conditions.p.rapidapi.com"  # skiapi (= Liftie)
FORECAST_HOST = "ski-resort-forecast.p.rapidapi.com"  # optional RapidAPI snow

# Attribution (data licenses). Surfaced on entities.
ATTRIBUTION = (
    "Ski-area data © OpenSkiMap (OpenStreetMap contributors & Skimap.org, ODbL); "
    "weather © Open-Meteo (CC-BY 4.0); lift status © Liftie (BSD)"
)
OPENSKIMAP_PERMALINK = "https://openskimap.org/?obj={id}"

# --- Config entry data keys ------------------------------------------------
CONF_AREA = "area"  # the bundled OpenSkiMap record snapshot (dict)
CONF_OPENSKIMAP_ID = "id"
CONF_NAME = "name"

# --- Options keys ----------------------------------------------------------
CONF_UNITS = "units"
CONF_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"
CONF_RAPIDAPI_KEY = "rapidapi_key"  # optional; unlocks RapidAPI snow + skiapi lifts
CONF_FORECAST_RESORT = "forecast_resort"  # RapidAPI snow-forecast resort name
CONF_LIFTIE_BASE_URL = "liftie_base_url"  # self-hosted Liftie base URL
CONF_LIFT_SLUG = "lift_slug"  # Liftie/skiapi slug (auto from crosswalk)

# Config-flow (search) keys
CONF_QUERY = "query"
CONF_COUNTRY = "country"
CONF_SKI_AREA = "ski_area"

# --- Units -----------------------------------------------------------------
UNIT_METRIC = "metric"
UNIT_IMPERIAL = "imperial"
UNITS = [UNIT_METRIC, UNIT_IMPERIAL]
DEFAULT_UNITS = UNIT_IMPERIAL
# Bundled data is SI (m, cm). Display conversion factors.
LENGTH_UNIT = {UNIT_METRIC: "cm", UNIT_IMPERIAL: "in"}
DEPTH_UNIT = {UNIT_METRIC: "cm", UNIT_IMPERIAL: "in"}
ELEV_UNIT = {UNIT_METRIC: "m", UNIT_IMPERIAL: "ft"}

# --- Defaults --------------------------------------------------------------
DEFAULT_SCAN_INTERVAL_MINUTES = 180
MIN_SCAN_INTERVAL_MINUTES = 60

# --- Coordinator data bundle keys ------------------------------------------
DATA_WEATHER = "weather"
DATA_SNOW = "snow"  # RapidAPI snow-forecast (optional)
DATA_LIFTS = "lifts"
DATA_AREA = "area"

# Weather bundle sub-keys
WX_TEMP = "temperature"
WX_WIND = "wind_speed"
WX_GUST = "wind_gust"
WX_HUMIDITY = "humidity"
WX_CONDITION = "condition"
WX_FRESH_SNOW = "fresh_snow"  # next-24h snowfall
WX_SNOW_DEPTH = "snow_depth"
WX_FREEZING_LEVEL = "freezing_level"
WX_DAILY = "daily"  # HA daily forecast list
WX_HOURLY = "hourly"  # HA hourly forecast list

# Difficulty ordering used for terrain sensors.
DIFFICULTIES = ["novice", "easy", "intermediate", "advanced", "expert", "freeride"]
