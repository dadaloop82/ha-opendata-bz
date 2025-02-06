"""
Home Assistant Integration - OpenData South Tyrol (Provincia di Bolzano)
https://github.com/dadaloop82/ha-opendata-bz

This module contains all constants used throughout the OpenData South Tyrol integration.
It provides configuration parameters, API endpoints, and translations for the integration.

Author: Daniel Stimpfl (@dadaloop82)
License: Apache License 2.0
"""

from typing import Final
from homeassistant.const import Platform

# Integration identifiers
DOMAIN: Final = "provbz_opendata"
NAME: Final = "OpenData Provincia Bolzano"
VERSION: Final = "1.1.0"

# Base API endpoint for the OpenData South Tyrol platform
BASE_API_URL: Final = "https://data.civis.bz.it/api/3/action"

# Configuration keys used in configuration.yaml
CONF_GROUP_ID = "group_id"          # Group identifier for data categorization
CONF_DATASET_ID = "dataset_id"      # Dataset identifier within a group
CONF_PACKAGE_ID = "package_id"      # Package identifier containing resources
CONF_RESOURCE_ID = "resource_id"    # Specific resource identifier
CONF_LANGUAGE = "language"          # Interface language selection
# Fields to be imported from the dataset
CONF_SELECTED_FIELDS = "selected_fields"

# Supported languages for the integration interface
SUPPORTED_LANGUAGES = {
    "en": "English",
    "it": "Italiano",
    "de": "Deutsch",
    "rm": "Ladin"
}

SUPPORTED_FORMATS = {
    "JSON": "JavaScript Object Notation",
    "WFS": "Web Feature Service",
    "XLSX": "Office Open XML Spreadsheet",
    "XLS": "Excel Binary File Format",
    "CSV": "Comma-Separated Values"
}

# Default configuration values
DEFAULT_LANGUAGE = "en"
DEFAULT_SCAN_INTERVAL = 300  # Update interval in seconds (5 minutes)
DEFAULT_ICON = "mdi:database"

# Supported Home Assistant platforms for this integration
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.DEVICE_TRACKER]

# WMS (Web Map Service) default configuration
WMS_MAP_DEFAULTS = {
    "bbox_default": "10.4,46.2,12.5,47.1",  # Bounding box for South Tyrol region
    "width": 2048,                          # Map width in pixels
    "height": 2048,                         # Map height in pixels
    "feature_count": 100,                   # Maximum features to return
    # Update interval in seconds (5 minutes)
    "scan_interval": 300,
}

XLSX_SUPPORTED_FORMATS = ["XLSX", "XLS"]
DEFAULT_XLSX_SCAN_INTERVAL = 3600  # 1 ora

# Multilingual translations for data groups
# These translations are used to provide user-friendly names for data categories
GROUP_TRANSLATIONS = {
    "it": {  # Italian translations
        "boundaries": "Confini",
        "climatologymeteorologyatmosphere": "Climatologia, Meteorologia e Atmosfera",
        "culture": "Cultura",
        "demography": "Demografia",
        "economy": "Economia",
        "environment": "Ambiente",
        "farming": "Agricoltura",
        "geoscientificinformation": "Informazioni Geoscientifiche",
        "healthiness": "Salute",
        "knlowledge": "Conoscenza",
        "mobility": "Mobilità",
        "political": "Politica",
        "security": "Sicurezza",
        "sport": "Sport",
        "tourism": "Turismo",
        "weather": "Meteo",
        "welfare": "Welfare"
    },
    "de": {  # German translations
        "boundaries": "Grenzen",
        "climatologymeteorologyatmosphere": "Klimatologie, Meteorologie und Atmosphäre",
        "culture": "Kultur",
        "demography": "Demographie",
        "economy": "Wirtschaft",
        "environment": "Umwelt",
        "farming": "Landwirtschaft",
        "geoscientificinformation": "Geowissenschaftliche Informationen",
        "healthiness": "Gesundheit",
        "knlowledge": "Wissen",
        "mobility": "Mobilität",
        "political": "Politik",
        "security": "Sicherheit",
        "sport": "Sport",
        "tourism": "Tourismus",
        "weather": "Wetter",
        "welfare": "Wohlfahrt"
    },
    "en": {  # English translations
        "boundaries": "Boundaries",
        "climatologymeteorologyatmosphere": "Climatology, Meteorology and Atmosphere",
        "culture": "Culture",
        "demography": "Demography",
        "economy": "Economy",
        "environment": "Environment",
        "farming": "Farming",
        "geoscientificinformation": "Geoscientific Information",
        "healthiness": "Healthiness",
        "knlowledge": "Knowledge",
        "mobility": "Mobility",
        "political": "Political",
        "security": "Security",
        "sport": "Sport",
        "tourism": "Tourism",
        "weather": "Weather",
        "welfare": "Welfare"
    }
}
