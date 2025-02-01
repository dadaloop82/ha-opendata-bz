# custom_components/provbz_opendata/const.py

"""Constants for the OpenData Provincia Bolzano integration."""
from typing import Final
from homeassistant.const import Platform

DOMAIN: Final = "opendata_provincia_bolzano"
NAME: Final = "OpenData Provincia Bolzano"
VERSION: Final = "1.0.0"

# API
BASE_API_URL: Final = "https://data.civis.bz.it/api/3/action"

# Configuration
CONF_GROUP_ID = "group_id"
CONF_DATASET_ID = "dataset_id"
CONF_PACKAGE_ID = "package_id"
CONF_RESOURCE_ID = "resource_id"
CONF_LANGUAGE = "language"
CONF_SELECTED_FIELDS = "selected_fields"

# Languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "it": "Italiano",
    "de": "Deutsch",
    "rm": "Ladin"
}

# Defaults
DEFAULT_LANGUAGE = "en"

# Scan interval
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

# Icons
DEFAULT_ICON = "mdi:database"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.DEVICE_TRACKER]

WMS_MAP_DEFAULTS = {
    "bbox_default": "10.4,46.2,12.5,47.1",  # Default bbox per Alto Adige
    "width": 2048,
    "height": 2048,
    "feature_count": 100,
    "scan_interval": 300,  # 5 minuti
}

GROUP_TRANSLATIONS = {
    "it": {
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
    "de": {
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
    "en": {
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