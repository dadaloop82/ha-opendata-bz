"""
Home Assistant Integration - OpenData South Tyrol (Provincia di Bolzano)
Device Tracker Platform for WFS (Web Feature Service) Layers

This module implements a device tracker platform that handles WFS layer data from the
OpenData South Tyrol API. It creates tracker entities for geographic features,
making them available on Home Assistant maps.

Author: Daniel Stimpfl (@dadaloop82)
License: Apache License 2.0
"""

from __future__ import annotations

import logging
from typing import Any
from datetime import timedelta

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OpenData trackers based on a config entry.

    Args:
        hass: Home Assistant instance
        entry: Configuration entry containing WFS layer settings
        async_add_entities: Callback to register new entities
    """
    entry_data = hass.data[DOMAIN][entry.entry_id]
    config = entry_data.get("config", {})

    # Skip setup if the resource is not a WFS layer
    if config.get("resource_format") != "WFS":
        return

    api = entry_data["api"]
    resource = next(
        (r for r in config.get("resources", [])
         if r["id"] == config.get("resource_id")),
        None
    )

    if not resource:
        _LOGGER.error("Resource not found in configuration")
        return

    async def async_update_data():
        """Fetch data from WFS endpoint.

        Returns:
            list: List of feature dictionaries containing geometry and properties
        """
        try:
            features = await api.get_wfs_features(
                config["resource_url"],
                resource.get("name", "")
            )

            if not isinstance(features, list):
                _LOGGER.error("Invalid features data type: %s", type(features))
                return []

            # Log first feature structure for debugging purposes
            if features and len(features) > 0:
                first_feature = features[0]
                _LOGGER.debug(
                    "WFS feature structure - Properties available: %s",
                    list(first_feature.get("properties", {}).keys())
                )

            return features

        except Exception as err:
            _LOGGER.error("Error updating WFS data: %s", err)
            return []

    # Initialize update coordinator for the WFS data
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_wfs_{config.get('resource_id', '')}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    # Create tracker entities for each WFS feature
    entities = []
    for feature in coordinator.data or []:
        if not isinstance(feature, dict):
            _LOGGER.error("Invalid feature type: %s", type(feature))
            continue

        entities.append(
            WFSPointEntity(
                coordinator,
                config,
                feature
            )
        )

    if entities:
        _LOGGER.info("Created %d WFS entities", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No valid WFS entities created")


class WFSPointEntity(CoordinatorEntity, TrackerEntity):
    """Representation of a WFS point feature as a trackable entity.

    This entity represents a geographic point from a WFS layer, making it
    visible on Home Assistant maps and providing its properties as attributes.
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config: dict,
        feature: dict,
    ) -> None:
        """Initialize the WFS point entity.

        Args:
            coordinator: The data update coordinator
            config: Configuration dictionary
            feature: WFS feature dictionary containing geometry and properties
        """
        super().__init__(coordinator)
        self._feature = feature
        self._properties = feature.get("properties", {})

        # Generate a meaningful name from feature ID or properties
        name_fields = self._get_name_fields()
        entity_name = " - ".join(str(v)
                                 for v in name_fields.values() if v is not None)
        if not entity_name:
            entity_name = f"Point {feature.get('id', 'unknown')}"

        self._attr_name = entity_name
        self._attr_unique_id = f"wfs_{config.get('resource_id')}_{feature.get('id', '')}"
        self._attr_icon = 'mdi:map-marker'

    def _get_name_fields(self) -> dict:
        """Extract name fields from feature properties.

        Looks for bilingual name pairs (DE/IT) first, then falls back to
        common name fields if bilingual names are not available.

        Returns:
            dict: Dictionary of field names and their values
        """
        name_fields = {}

        # Look for DE/IT field pairs
        for key in self._properties:
            if key.endswith('_DE'):
                base_name = key[:-3]
                it_key = f"{base_name}_IT"
                if it_key in self._properties:
                    name_fields[base_name] = f"{self._properties[key]} - {self._properties[it_key]}"

        # Fallback to common name fields if no DE/IT pairs found
        if not name_fields:
            name_candidates = ["name", "NAME", "title",
                               "TITLE", "description", "DESCRIPTION"]
            for key in name_candidates:
                if key in self._properties:
                    name_fields["name"] = self._properties[key]
                    break

        return name_fields

    @property
    def state(self) -> str:
        """Return the state of the entity.

        Returns:
            str: Always returns 'present' as WFS points are static
        """
        return "present"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Provide additional attributes from feature properties.

        Returns:
            dict: Dictionary of all non-null feature properties
        """
        return {
            k: v for k, v in self._properties.items()
            if v is not None  # Exclude null values
        }

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the WFS point.

        Returns:
            float or None: Latitude value if available
        """
        try:
            return self._feature["geometry"]["coordinates"][1]
        except (KeyError, IndexError):
            return None

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the WFS point.

        Returns:
            float or None: Longitude value if available
        """
        try:
            return self._feature["geometry"]["coordinates"][0]
        except (KeyError, IndexError):
            return None
