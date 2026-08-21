"""Constants for the Ski Resort Forecast integration."""

from __future__ import annotations

DOMAIN = "ski_resort"
MANUFACTURER = "Ski Resort Forecast"

# --- RapidAPI hosts ----------------------------------------------------------
# One RapidAPI key unlocks both products; the ``X-RapidAPI-Host`` header selects
# which one a request targets. The forecast product is the core data source
# (snow depth + fresh snow + 3/5-day forecast); the conditions product is an
# optional add-on for live lift counts and is gated by an options toggle.
FORECAST_HOST = "ski-resort-forecast.p.rapidapi.com"
CONDITIONS_HOST = "ski-resorts-and-conditions.p.rapidapi.com"

# --- Config keys (entry.data) ------------------------------------------------
CONF_API_KEY = "api_key"
CONF_RESORT = "resort"  # forecast-API resort name, e.g. "Vail"
CONF_NAME = "name"  # friendly display name for the device

# --- Option keys (entry.options) ---------------------------------------------
CONF_UNITS = "units"  # "imperial" | "metric"
CONF_ELEVATION = "elevation"  # "top" | "mid" | "bot"
CONF_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"
# Lift status hits a second RapidAPI product, so it gets a toggle that gates the
# fetch (same convention as this project's forecast core: only pay for a call
# when the feature is on).
CONF_ENABLE_LIFTS = "lifts_enabled"
CONF_LIFT_SLUG = "lift_slug"  # skiapi resort slug, e.g. "vail"

# --- Units -------------------------------------------------------------------
UNIT_IMPERIAL = "imperial"
UNIT_METRIC = "metric"
UNITS = [UNIT_IMPERIAL, UNIT_METRIC]
# Query-param value + display unit for each system.
UNIT_QUERY = {UNIT_IMPERIAL: "i", UNIT_METRIC: "m"}
LENGTH_UNIT = {UNIT_IMPERIAL: "in", UNIT_METRIC: "cm"}

# --- Elevations --------------------------------------------------------------
ELEVATIONS = ["top", "mid", "bot"]

# --- Defaults ----------------------------------------------------------------
DEFAULT_UNITS = UNIT_IMPERIAL
DEFAULT_ELEVATION = "top"
# Snow reports refresh a few times a day; the source data does not move faster
# than that and RapidAPI free tiers are quota-limited, so poll conservatively.
DEFAULT_SCAN_INTERVAL_MINUTES = 360
MIN_SCAN_INTERVAL_MINUTES = 30
DEFAULT_ENABLE_LIFTS = False

# --- Coordinator data-bundle keys --------------------------------------------
DATA_SNOW = "snow"  # parsed snowConditions
DATA_FORECAST = "forecast"  # raw forecast payload
DATA_LIFTS = "lifts"  # parsed lift stats, or None when disabled/unavailable
DATA_INFO = "info"  # basicInfo (name/region/coords/elevations)

# Snow-condition sub-keys (normalized in the coordinator).
SNOW_FRESH = "fresh"
SNOW_TOP = "top_depth"
SNOW_BASE = "base_depth"
SNOW_LAST_DATE = "last_snow_date"
SNOW_TOP_TREND = "top_trend"  # "up" | "down" | "stable"
SNOW_TOP_CHANGE = "top_change"  # numeric delta vs previous poll
