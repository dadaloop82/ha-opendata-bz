"""
OpenData Alto Adige (OpenData Südtirol) API Client.

This module provides the API client for interacting with the OpenData Hub
of the Autonomous Province of Bolzano/Bozen. It handles API calls, WFS/WMS 
requests and data parsing.

Project: ha-opendata-bz
Author: Daniel Stimpfl (@dadaloop82)
License: Apache License 2.0
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import HomeAssistantError

from .const import BASE_API_URL

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Exception raised when API connection fails."""


class OpenDataBolzanoApiClient:
    """API client for the OpenData Alto Adige Hub.

    This class manages all API interactions including:
    - Core API requests
    - WFS (Web Feature Service) requests
    - WMS (Web Map Service) requests
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the API client.

        Args:
            hass: HomeAssistant instance for session management
        """
        self._hass = hass
        self._session = async_get_clientsession(hass)

    async def _api_call(self, endpoint: str, params: dict | None = None) -> Any:
        """Make a call to the OpenData API.

        Args:
            endpoint: API endpoint to call
            params: Optional query parameters

        Returns:
            API response data

        Raises:
            CannotConnect: If the API call fails
        """
        url = f"{BASE_API_URL}/{endpoint}"

        try:
            async with async_timeout.timeout(120):
                _LOGGER.debug(
                    "Making API call to %s with params %s", url, params)
                async with self._session.get(url, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if data.get("success") is False:
                        error_msg = data.get("error", {}).get(
                            "message", "Unknown error")
                        _LOGGER.error("API error for %s: %s",
                                      endpoint, error_msg)
                        raise CannotConnect

                    result = data.get("result")
                    _LOGGER.debug(
                        "API call successful, received data: %s", result)
                    return result

        except aiohttp.ClientError as err:
            _LOGGER.error("Error connecting to API: %s", err)
            raise CannotConnect from err
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout connecting to API: %s", err)
            raise CannotConnect from err
        except Exception as err:
            _LOGGER.error("Unexpected error in API call: %s", err)
            raise CannotConnect from err

    async def get_groups(self) -> list[dict[str, Any]]:
        """Get list of available data groups.

        Returns:
            List of group dictionaries
        """
        return await self._api_call("group_list", {"all_fields": "true"})

    async def get_group_details(self, group_id: str) -> dict[str, Any]:
        """Get detailed information for a specific group.

        Args:
            group_id: ID of the group to fetch

        Returns:
            Group details dictionary
        """
        _LOGGER.debug("Getting details for group: %s", group_id)
        return await self._api_call("group_show", {
            "id": group_id,
            "include_datasets": "true"
        })

    async def get_package_details(self, package_id: str) -> dict[str, Any]:
        """Get detailed information for a specific data package.

        Args:
            package_id: ID of the package to fetch

        Returns:
            Package details dictionary
        """
        return await self._api_call("package_show", {"id": package_id})

    async def get_group_packages(self, group_id: str) -> list[dict[str, Any]]:
        """Get list of data packages within a group.

        Args:
            group_id: ID of the group to fetch packages from

        Returns:
            List of package dictionaries

        Raises:
            CannotConnect: If fetching packages fails
        """
        try:
            _LOGGER.debug("Fetching packages for group: %s", group_id)
            group_data = await self.get_group_details(group_id)
            _LOGGER.debug("Group data received: %s", group_data)

            packages = group_data.get("packages", [])
            _LOGGER.debug("Retrieved %d packages for group %s",
                          len(packages), group_id)
            return packages
        except Exception as err:
            _LOGGER.error("Error getting group packages: %s", err)
            raise

    async def get_resource_data(self, url: str) -> dict[str, Any] | list[dict[str, Any]]:
        """Get data from a resource URL.

        Handles both direct JSON resources and WFS services by converting
        WFS responses to GeoJSON format.

        Args:
            url: Resource URL to fetch data from

        Returns:
            Resource data as dictionary or list

        Raises:
            CannotConnect: If fetching resource data fails
        """
        try:
            async with async_timeout.timeout(10):
                _LOGGER.debug("Fetching resource data from URL: %s", url)
                async with self._session.get(url) as response:
                    response.raise_for_status()

                    content_type = response.headers.get('Content-Type', '')

                    if 'excel' in content_type or 'xls' in content_type:
                        _LOGGER.debug("Excel file detected, skipping JSON parsing")
                        return {"rows": []}

                    if 'xml' in content_type.lower():
                        _LOGGER.debug("XML response detected, parsing as WFS")
                        # Convert WFS to JSON request
                        url_parts = list(urlparse(url))
                        query = dict(parse_qs(url_parts[4]))
                        query.update({
                            'REQUEST': 'GetFeature',
                            'OUTPUTFORMAT': 'application/json'
                        })
                        url_parts[4] = urlencode(query, True)
                        new_url = urlunparse(url_parts)

                        # Make JSON request
                        async with self._session.get(new_url) as json_response:
                            json_response.raise_for_status()
                            data = await json_response.json()
                            return data.get('features', [])
                    else:
                        data = await response.json()
                        _LOGGER.debug("Resource data retrieved successfully")
                        return data

        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching resource data: %s", err)
            raise CannotConnect from err
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout fetching resource data: %s", err)
            raise CannotConnect from err
        except Exception as err:
            _LOGGER.error("Unexpected error fetching resource data: %s", err)
            raise CannotConnect from err

    async def get_wfs_features(self, wfs_url: str, layer_name: str) -> list:
        """Get features from a WFS service.

        Args:
            wfs_url: WFS service URL
            layer_name: Name of the layer to fetch

        Returns:
            List of GeoJSON features
        """
        params = {
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetFeature",
            "TYPENAME": layer_name,
            "OUTPUTFORMAT": "application/json",
            "SRSNAME": "EPSG:4326",
            "COUNT": "1000"  # Limit features for performance
        }

        try:
            async with async_timeout.timeout(30):
                _LOGGER.debug(
                    "WFS request to: %s with params: %s", wfs_url, params)
                async with self._session.get(wfs_url, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    _LOGGER.debug("WFS response received with %d features",
                                  len(data.get("features", [])))
                    return data.get("features", [])

        except Exception as err:
            _LOGGER.error("Error getting WFS features: %s", err)
            return []

    async def get_resource_binary(self, url: str) -> bytes:
        """Get binary data from a resource URL.

        Args:
            url: Resource URL to fetch data from

        Returns:
            Binary data as bytes

        Raises:
            CannotConnect: If fetching resource data fails
        """
        try:
            # Timeout più lungo per file grandi
            async with async_timeout.timeout(30):
                _LOGGER.debug("Fetching binary data from URL: %s", url)
                async with self._session.get(url) as response:
                    response.raise_for_status()
                    data = await response.read()
                    _LOGGER.debug(
                        "Binary data retrieved successfully, size: %d bytes", len(data))
                    return data

        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching binary data: %s", err)
            raise CannotConnect from err
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout fetching binary data: %s", err)
            raise CannotConnect from err
        except Exception as err:
            _LOGGER.error("Unexpected error fetching binary data: %s", err)
            raise CannotConnect from err

    async def get_feature_info(self, wms_url: str, layer_name: str, bbox: str) -> list:
        """Get feature information from a WMS service.

        Args:
            wms_url: WMS service URL
            layer_name: Name of the layer to query
            bbox: Bounding box for the query

        Returns:
            List of features
        """
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetFeatureInfo",
            "LAYERS": layer_name,
            "QUERY_LAYERS": layer_name,
            "INFO_FORMAT": "application/json",
            "FEATURE_COUNT": "100",
            "BBOX": bbox,
            "WIDTH": "2048",
            "HEIGHT": "2048",
            "CRS": "EPSG:4326",
            "I": "1024",
            "J": "1024",
            "EXCEPTIONS": "application/json",
            "STYLES": "",
            "FORMAT": "image/png",
            "TRANSPARENT": "TRUE"
        }

        try:
            async with async_timeout.timeout(30):
                _LOGGER.debug("WMS GetFeatureInfo request: %s", wms_url)
                async with self._session.get(wms_url, params=params) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "")

                    if "application/json" in content_type:
                        data = await response.json()
                        _LOGGER.debug("Received JSON response: %s", data)
                        return data.get("features", [])
                    else:
                        text = await response.text()
                        _LOGGER.error(
                            "Unexpected response type: %s, content: %s",
                            content_type, text[:200])
                        return []

        except Exception as err:
            _LOGGER.error("Error getting WMS feature info: %s", err)
            _LOGGER.debug("URL was: %s", wms_url)
            return []
