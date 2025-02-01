"""Sensor platform for OpenData Provincia Bolzano."""
from __future__ import annotations

import logging
import re
from typing import Any
from datetime import timedelta

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DOMAIN,
    CONF_RESOURCE_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_ICON
)
from .api import OpenDataBolzanoApiClient, CannotConnect

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OpenData Provincia Bolzano sensors based on a config entry."""
    _LOGGER.debug("Setting up sensors for entry: %s", entry.entry_id)

    # Recupera i dati salvati durante la configurazione
    entry_data = hass.data[DOMAIN][entry.entry_id]
    api = entry_data["api"]
    config = entry_data["config"]
    rows_data = entry_data.get("rows_data", [])

    _LOGGER.debug("Entry data loaded - Config: %s", config)
    _LOGGER.debug("Rows data loaded - Length: %d", len(rows_data))

    async def async_update_data():
        """Fetch data from API."""
        try:
            url = config.get("resource_url")
            if not url:
                _LOGGER.error("No resource URL found in config")
                return rows_data

            _LOGGER.debug("Fetching data from URL: %s", url)
            data = await api.get_resource_data(url)

            if isinstance(data, dict) and "rows" in data:
                return data["rows"]
            elif isinstance(data, list):
                return data

            _LOGGER.warning("Unexpected data format received")
            return rows_data

        except Exception as err:
            _LOGGER.error("Error fetching data: %s", err)
            return rows_data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    # Imposta i dati iniziali nel coordinator
    coordinator.data = rows_data

    entities = []
    selected_rows = config.get("selected_rows", [])
    selected_fields = config.get("selected_fields", [])

    _LOGGER.debug("Creating sensors for rows: %s", selected_rows)
    _LOGGER.debug("With fields: %s", selected_fields)

    # Crea un sensore per ogni campo selezionato di ogni riga selezionata
    for row_idx in selected_rows:
        if row_idx >= len(rows_data):
            _LOGGER.error(
                "Row index %d out of range (total rows: %d)", row_idx, len(rows_data))
            continue

        row = rows_data[row_idx]
        row_name = row.get("name", f"row_{row_idx}")

        for field_type, key in selected_fields:
            try:
                if field_type == "measurement":
                    # Cerca la misurazione con il codice corrispondente
                    measurement = next(
                        (m for m in row.get("measurements", [])
                         if m.get("code", "").lower() == key.lower()),
                        None
                    )
                    if measurement:
                        _LOGGER.debug(
                            "Creating measurement sensor: %s - %s",
                            row_name,
                            measurement.get("description", key)
                        )
                        sensor = OpenDataSensor(
                            coordinator,
                            entry,
                            row_idx,
                            key,
                            row_name,
                            measurement.get("description", key),
                            field_type
                        )
                        entities.append(sensor)
                else:
                    _LOGGER.debug(
                        "Creating field sensor: %s - %s",
                        row_name,
                        key
                    )
                    sensor = OpenDataSensor(
                        coordinator,
                        entry,
                        row_idx,
                        key,
                        row_name,
                        key,
                        field_type
                    )
                    entities.append(sensor)
            except Exception as err:
                _LOGGER.error(
                    "Error creating sensor for %s - %s: %s",
                    row_name,
                    key,
                    err
                )

    if not entities:
        _LOGGER.warning(
            "No sensors were created for entry %s",
            entry.entry_id
        )
    else:
        _LOGGER.info(
            "Created %d sensors for entry %s",
            len(entities),
            entry.entry_id
        )

    async_add_entities(entities)


class OpenDataSensor(CoordinatorEntity, SensorEntity):
    """Representation of an OpenData Sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        row_idx: int,
        field: str,
        row_name: str,
        description: str,
        field_type: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._row_idx = row_idx
        self._field = field
        self._field_type = field_type
        self._config_entry = config_entry

        # Genera l'ID univoco
        self._attr_unique_id = (
            f"{config_entry.entry_id}_{row_idx}_{field_type}_{field}"
        )

        # Crea nomi puliti per l'entity_id
        clean_row_name = re.sub(r'[^a-z0-9_]+', '_', row_name.lower().strip())
        clean_description = re.sub(
            r'[^a-z0-9_]+', '_', description.lower().strip())

        # Rimuovi underscore multipli e trim
        clean_row_name = re.sub(r'_+', '_', clean_row_name).strip('_')
        clean_description = re.sub(r'_+', '_', clean_description).strip('_')

        self.entity_id = f"sensor.provbz_{clean_row_name}_{clean_description}"
        self._attr_name = f"{row_name} {description}"

        # Imposta l'icona di default
        self._attr_icon = DEFAULT_ICON

        _LOGGER.debug(
            "Initialized sensor %s (entity_id: %s, unique_id: %s)",
            self._attr_name,
            self.entity_id,
            self._attr_unique_id
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        try:
            if self._row_idx >= len(self.coordinator.data):
                return None

            row = self.coordinator.data[self._row_idx]
            return row.get(self._field)
        except (IndexError, KeyError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}

        try:
            row = self.coordinator.data[self._row_idx]
            return {
                k: v for k, v in row.items()
                if k != self._field and k != "measurements"
            }
        except (IndexError, KeyError):
            return {}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data:
            return False

        try:
            return self._row_idx < len(self.coordinator.data)
        except:
            return False
