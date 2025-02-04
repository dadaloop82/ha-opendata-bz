"""
Home Assistant Integration - OpenData South Tyrol (Provincia di Bolzano)
Sensor Platform Implementation

This module implements the sensor platform for the OpenData South Tyrol integration.
It creates sensor entities based on the data retrieved from the OpenData API,
supporting regular fields, measurement-type data, and XLSX files.

Author: Daniel Stimpfl (@dadaloop82)
License: Apache License 2.0
"""

from __future__ import annotations

import logging
import re
from typing import Any
from datetime import timedelta
import pandas as pd
import io

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
    DEFAULT_ICON,
    XLSX_SUPPORTED_FORMATS,
    DEFAULT_XLSX_SCAN_INTERVAL
)
from .api import OpenDataBolzanoApiClient, CannotConnect

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OpenData South Tyrol sensors based on a config entry."""
    _LOGGER.debug("Setting up sensors for entry: %s", entry.entry_id)

    entry_data = hass.data[DOMAIN][entry.entry_id]
    api = entry_data["api"]
    config = entry_data["config"]
    
    # Determine the resource format and handle accordingly
    resource_format = config.get("resource_format", "").upper()
    
    if resource_format in XLSX_SUPPORTED_FORMATS:
        await setup_xlsx_sensors(hass, entry, entry_data, async_add_entities)
    else:
        await setup_standard_sensors(hass, entry, entry_data, async_add_entities)


async def setup_standard_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    entry_data: dict,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up standard (non-XLSX) sensors."""
    api = entry_data["api"]
    config = entry_data["config"]
    rows_data = entry_data.get("rows_data", [])

    async def async_update_data():
        """Fetch data from API."""
        try:
            url = config.get("resource_url")
            if not url:
                _LOGGER.error("No resource URL found in config")
                return rows_data

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

    coordinator.data = rows_data
    
    entities = []
    selected_rows = config.get("selected_rows", [])
    selected_fields = config.get("selected_fields", [])

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
                    measurement = next(
                        (m for m in row.get("measurements", [])
                         if m.get("code", "").lower() == key.lower()),
                        None
                    )
                    if measurement:
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

    if entities:
        _LOGGER.info(
            "Created %d sensors for entry %s",
            len(entities),
            entry.entry_id
        )
        async_add_entities(entities)


async def setup_xlsx_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    entry_data: dict,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors for XLSX data sources."""
    api = entry_data["api"]
    config = entry_data["config"]
    selected_row_idx = config["selected_rows"][0]  # Prendiamo l'indice della riga selezionata
    selected_fields = config["selected_fields"]    # Prendiamo i campi selezionati

    async def async_update_xlsx_data():
        """Fetch data from XLSX file."""
        try:
            url = config.get("resource_url")
            if not url:
                _LOGGER.error("No resource URL found in config")
                return []

            _LOGGER.debug("Fetching XLSX data from URL: %s", url)
            response = await api.get_resource_binary(url)
            
            df = pd.read_excel(io.BytesIO(response))
            return df.to_dict('records')

        except Exception as err:
            _LOGGER.error("Error fetching XLSX data: %s", err)
            return []

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_xlsx_{entry.entry_id}",
        update_method=async_update_xlsx_data,
        update_interval=timedelta(seconds=DEFAULT_XLSX_SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.data:
        _LOGGER.error("No data received from XLSX file")
        return

    entities = []
    row = coordinator.data[selected_row_idx]
    base_name = str(row.get(list(row.keys())[0], f"row_{selected_row_idx}"))

    # Creiamo solo i sensori per i campi selezionati
    for field_type, column in selected_fields:
        clean_column = re.sub(r'[^a-z0-9_]+', '_', column.lower().strip())
        sensor = OpenDataXLSXSensor(
            coordinator,
            entry,
            selected_row_idx,
            column,
            base_name,
            clean_column
        )
        entities.append(sensor)

    if entities:
        _LOGGER.info(
            "Created %d XLSX sensors for entry %s",
            len(entities),
            entry.entry_id
        )
        async_add_entities(entities)


class OpenDataSensor(CoordinatorEntity, SensorEntity):
    """Representation of an OpenData South Tyrol sensor."""

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

        self._attr_unique_id = (
            f"{config_entry.entry_id}_{row_idx}_{field_type}_{field}"
        )

        clean_row_name = re.sub(r'[^a-z0-9_]+', '_', row_name.lower().strip())
        clean_description = re.sub(
            r'[^a-z0-9_]+', '_', description.lower().strip())

        clean_row_name = re.sub(r'_+', '_', clean_row_name).strip('_')
        clean_description = re.sub(r'_+', '_', clean_description).strip('_')

        self.entity_id = f"sensor.provbz_{clean_row_name}_{clean_description}"
        self._attr_name = f"{row_name} {description}"
        self._attr_icon = DEFAULT_ICON

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data or self._row_idx >= len(self.coordinator.data):
            return None

        try:
            row = self.coordinator.data[self._row_idx]
            return row.get(self._field)
        except (IndexError, KeyError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes from the data row."""
        if not self.coordinator.data or self._row_idx >= len(self.coordinator.data):
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
        """Return if the sensor is available."""
        if not self.coordinator.data:
            return False

        try:
            return self._row_idx < len(self.coordinator.data)
        except:
            return False


class OpenDataXLSXSensor(CoordinatorEntity, SensorEntity):
    """Representation of an OpenData XLSX sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        row_idx: int,
        column: str,
        base_name: str,
        clean_column: str
    ) -> None:
        """Initialize the XLSX sensor."""
        super().__init__(coordinator)
        self._row_idx = row_idx
        self._column = column
        
        # Create unique ID and entity ID
        self._attr_unique_id = f"{config_entry.entry_id}_xlsx_{row_idx}_{clean_column}"
        
        # Clean up base_name for entity_id
        clean_base_name = re.sub(r'[^a-z0-9_]+', '_', base_name.lower().strip())
        clean_base_name = re.sub(r'_+', '_', clean_base_name).strip('_')
        
        self.entity_id = f"sensor.provbz_xlsx_{clean_base_name}_{clean_column}"
        self._attr_name = f"{base_name} {column}"
        self._attr_icon = "mdi:file-excel"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data or self._row_idx >= len(self.coordinator.data):
            return None
            
        try:
            row = self.coordinator.data[self._row_idx]
            return row.get(self._column)
        except (IndexError, KeyError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes from the Excel row."""
        if not self.coordinator.data or self._row_idx >= len(self.coordinator.data):
            return {}
            
        try:
            row = self.coordinator.data[self._row_idx]
            return {
                k: v for k, v in row.items()
                if k != self._column
            }
        except (IndexError, KeyError):
            return {}