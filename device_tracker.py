"""Device tracker platform for OpenData Provincia Bolzano WFS layers."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .api import OpenDataBolzanoApiClient
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OpenData trackers based on config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    config = entry_data.get("config", {})

    # Verifica se questa entry è per un layer WFS
    if config.get("resource_format") != "WFS":
        return

    api = entry_data["api"]
    resource = next((r for r in config.get("resources", [])
                    if r["id"] == config.get("resource_id")), None)

    if not resource:
        _LOGGER.error("Resource not found")
        return

    async def async_update_data():
        """Fetch data from WFS."""
        try:
            features = await api.get_wfs_features(
                config["resource_url"],
                resource.get("name", "")
            )

            if not isinstance(features, list):
                _LOGGER.error("Invalid features data type: %s", type(features))
                return []

            # Log della struttura del primo feature per debug
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

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_wfs_{config.get('resource_id', '')}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

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
    """Representation of a WFS point entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config: dict,
        feature: dict,
    ) -> None:
        """Initialize the WFS point."""
        super().__init__(coordinator)
        self._feature = feature
        self._properties = feature.get("properties", {})
        
        # Ottieni un nome significativo dall'ID della feature o dalle properties
        name_fields = self._get_name_fields()
        entity_name = " - ".join(str(v) for v in name_fields.values() if v is not None)
        if not entity_name:
            entity_name = f"Point {feature.get('id', 'unknown')}"
            
        self._attr_name = entity_name
        self._attr_unique_id = f"wfs_{config.get('resource_id')}_{feature.get('id', '')}"

        # Imposta l'icona base
        self._attr_icon = 'mdi:map-marker'

    def _get_name_fields(self) -> dict:
        """Get name fields based on available properties."""
        name_fields = {}
        
        # Cerca coppie di campi con suffisso _DE e _IT
        for key in self._properties:
            if key.endswith('_DE'):
                base_name = key[:-3]
                it_key = f"{base_name}_IT"
                if it_key in self._properties:
                    name_fields[base_name] = f"{self._properties[key]} - {self._properties[it_key]}"
        
        # Se non trova coppie DE/IT, cerca altri campi comuni per il nome
        if not name_fields:
            name_candidates = ["name", "NAME", "title", "TITLE", "description", "DESCRIPTION"]
            for key in name_candidates:
                if key in self._properties:
                    name_fields["name"] = self._properties[key]
                    break
        
        return name_fields

    @property
    def state(self) -> str:
        """Return state."""
        return "present"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        # Restituisce tutte le properties come attributi
        filtered_properties = {
            k: v for k, v in self._properties.items()
            if v is not None  # Esclude valori nulli
        }
        return filtered_properties

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the point."""
        try:
            return self._feature["geometry"]["coordinates"][1]
        except (KeyError, IndexError):
            return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the point."""
        try:
            return self._feature["geometry"]["coordinates"][0]
        except (KeyError, IndexError):
            return None