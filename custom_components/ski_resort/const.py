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
NWS_HOST = "api.weather.gov"  # US weather alerts (public domain)
AVALANCHE_HOST = "api.avalanche.org"  # US avalanche danger (avalanche.org)
AVALANCHE_CA_HOST = "avcan-services-api.prod.avalanche.ca"  # Avalanche Canada
# NWS requires a descriptive User-Agent on every request.
NWS_USER_AGENT = "home-assistant-ski_resort (https://github.com/yieldhog/ski-resort-ha)"

# Attribution (data licenses). Surfaced on entities.
ATTRIBUTION = (
    "Ski-area data © OpenSkiMap (OpenStreetMap contributors & Skimap.org, ODbL); "
    "weather © Open-Meteo (CC-BY 4.0); lift status © Liftie (BSD)"
)
OPENSKIMAP_PERMALINK = "https://openskimap.org/?obj={id}"
SKIMAP_PERMALINK = "https://skimap.org/skiareas/view/{id}"
WIKIDATA_PERMALINK = "https://www.wikidata.org/wiki/{id}"
COMMONS_FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/{name}"
WIKIDATA_HOST = "www.wikidata.org"
SKIMAP_HOST = "skimap.org"

# --- Config entry data keys ------------------------------------------------
CONF_AREA = "area"  # the bundled OpenSkiMap record snapshot (dict)
CONF_OPENSKIMAP_ID = "id"
CONF_NAME = "name"

# --- Options keys ----------------------------------------------------------
CONF_UNITS = "units"
CONF_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"
CONF_RAPIDAPI_KEY = "rapidapi_key"  # optional; unlocks RapidAPI snow + skiapi lifts
CONF_FORECAST_RESORT = "forecast_resort"  # RapidAPI snow-forecast resort name
CONF_FORECAST_INTERVAL_HOURS = "forecast_interval_hours"  # throttle RapidAPI snow polls
CONF_LIFTIE_BASE_URL = "liftie_base_url"  # self-hosted Liftie base URL
CONF_LIFT_SLUG = "lift_slug"  # Liftie/skiapi slug (auto from crosswalk)
CONF_WEBCAM_URL = "webcam_url"  # optional direct still-image webcam URL
CONF_ENABLE_ALERTS = "enable_alerts"  # US NWS weather alerts (on by default, US)
CONF_ENABLE_AVALANCHE = "enable_avalanche"  # avalanche.org danger (opt-in)
CONF_AVALANCHE_CENTER = "avalanche_center"  # optional center id override (auto-detected)

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
# NWS weather alerts are free, keyless, and US public-domain, so they're on by
# default — but only ever fetched for US resorts (NWS has no coverage
# elsewhere), so a worldwide resort makes no pointless call.
DEFAULT_ENABLE_ALERTS = True
DEFAULT_SCAN_INTERVAL_MINUTES = 180
MIN_SCAN_INTERVAL_MINUTES = 60
# The RapidAPI snow-forecast source is metered; poll it far less often than the
# main coordinator (reported depths change ~daily) to stay under free quotas.
DEFAULT_FORECAST_INTERVAL_HOURS = 12
MIN_FORECAST_INTERVAL_HOURS = 1

# --- Coordinator data bundle keys ------------------------------------------
DATA_WEATHER = "weather"
DATA_SNOW = "snow"  # RapidAPI snow-forecast (optional)
DATA_LIFTS = "lifts"
DATA_AREA = "area"
DATA_INFO = "info"  # enrichment: photo, trail map, operator, opening year
DATA_ALERTS = "alerts"  # NWS active weather alerts (optional)
DATA_AVALANCHE = "avalanche"  # avalanche.org danger for the resort's zone (optional)

# Weather bundle sub-keys
WX_TEMP = "temperature"
WX_APPARENT = "apparent_temperature"  # "feels like" (wind chill + humidity + sun)
WX_WIND = "wind_speed"
WX_GUST = "wind_gust"
WX_HUMIDITY = "humidity"
WX_CONDITION = "condition"
WX_FRESH_SNOW = "fresh_snow"  # next-24h snowfall
WX_SNOW_DEPTH = "snow_depth"
WX_FREEZING_LEVEL = "freezing_level"
WX_DAILY = "daily"  # HA daily forecast list
WX_HOURLY = "hourly"  # HA hourly forecast list

# Number of forecast days summarized by the snow-forecast sensor.
SNOW_FORECAST_DAYS = 5

# Difficulty ordering used for terrain sensors.
DIFFICULTIES = ["novice", "easy", "intermediate", "advanced", "expert", "freeride"]
