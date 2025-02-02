"""
OpenData Alto Adige (OpenData Südtirol) Integration for Home Assistant.

This integration allows you to integrate various public data sources from 
the OpenData Hub of the Autonomous Province of Bolzano/Bozen into your 
Home Assistant instance.

Project: ha-opendata-bz
Author: Daniel Stimpfl (@dadaloop82)
License: Apache License 2.0
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .api import OpenDataBolzanoApiClient

_LOGGER = logging.getLogger(__name__)

# Define supported platforms for the integration
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.DEVICE_TRACKER]

# Basic configuration schema
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({})
    },
    extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """
    Initial setup of the integration.

    This function is called when the integration is first loaded.
    It initializes the base configuration space in hass.data.

    Args:
        hass: HomeAssistant instance
        config: Configuration data

    Returns:
        bool: True if setup was successful
    """
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up a config entry for OpenData Alto Adige.

    This function is called when adding a new integration instance through
    the UI. It initializes the API client and sets up the selected platforms.

    Args:
        hass: HomeAssistant instance
        entry: Configuration entry containing user selections

    Returns:
        bool: True if entry setup was successful
    """
    hass.data.setdefault(DOMAIN, {})

    _LOGGER.debug("Setting up entry with data: %s", dict(entry.data))

    # Extract configuration data
    config_data = dict(entry.data)
    rows_data = config_data.get("rows_data", [])
    resources = config_data.get("resources", [])

    # Initialize API client
    api = OpenDataBolzanoApiClient(hass)

    # Store entry data for platform access
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "config": config_data,
        "rows_data": rows_data,
        "resources": resources
    }

    # Set up selected platforms (sensor and/or device_tracker)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Unload a config entry.

    This function is called when removing an integration instance.
    It ensures proper cleanup of platforms and data.

    Args:
        hass: HomeAssistant instance
        entry: Configuration entry to be removed

    Returns:
        bool: True if unload was successful
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Reload a config entry.

    This function handles reloading of an entry after configuration changes.

    Args:
        hass: HomeAssistant instance
        entry: Configuration entry to be reloaded
    """
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Handle configuration entry updates.

    This function is called when configuration changes are made.

    Args:
        hass: HomeAssistant instance
        entry: Updated configuration entry
    """
    await async_reload_entry(hass, entry)
