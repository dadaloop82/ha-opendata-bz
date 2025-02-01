# custom_components/provbz_opendata/api.py

"""API client for OpenData Provincia Bolzano."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import HomeAssistantError

from .const import BASE_API_URL

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class OpenDataBolzanoApiClient:
    """API client for OpenData Provincia Bolzano."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the client."""
        self._hass = hass
        self._session = async_get_clientsession(hass)

    async def _api_call(self, endpoint: str, params: dict | None = None) -> Any:
        """Make an API call."""
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
        """Get list of available groups."""
        return await self._api_call("group_list", {"all_fields": "true"})

    async def get_group_details(self, group_id: str) -> dict[str, Any]:
        """Get details for a specific group."""
        _LOGGER.debug("Getting details for group: %s", group_id)
        return await self._api_call("group_show", {"id": group_id, "include_datasets": "true"})

    async def get_package_details(self, package_id: str) -> dict[str, Any]:
        """Get details for a specific package."""
        return await self._api_call("package_show", {"id": package_id})

    async def get_group_packages(self, group_id: str) -> list[dict[str, Any]]:
        """Get list of packages in a group."""
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
        """Get data from a resource URL."""
        try:
            async with async_timeout.timeout(10):
                _LOGGER.debug("Fetching resource data from URL: %s", url)
                async with self._session.get(url) as response:
                    response.raise_for_status()

                    content_type = response.headers.get('Content-Type', '')
                    if 'xml' in content_type.lower():
                        _LOGGER.debug("XML response detected, parsing as WFS")
                        # Per WFS, modifica l'URL per richiedere JSON
                        url_parts = list(urlparse(url))
                        query = dict(parse_qs(url_parts[4]))
                        query.update({
                            'REQUEST': 'GetFeature',
                            'OUTPUTFORMAT': 'application/json'
                        })
                        url_parts[4] = urlencode(query, True)
                        new_url = urlunparse(url_parts)

                        # Fai una nuova richiesta per il JSON
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

    async def get_feature_info(self, wms_url: str, layer_name: str, bbox: str) -> list:
        """Get feature info from WMS."""
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
                _LOGGER.debug(
                    "WMS GetFeatureInfo request to URL: %s with params: %s", wms_url, params)
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
                            "Unexpected response type: %s, content: %s", content_type, text[:200])
                        return []

        except Exception as err:
            _LOGGER.error("Error getting WMS feature info: %s", err)
            _LOGGER.debug("URL was: %s", wms_url)
            return []

    async def get_wfs_features(self, wfs_url: str, layer_name: str) -> list:
        """Get features from WFS."""
        params = {
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetFeature",
            "TYPENAME": layer_name,
            "OUTPUTFORMAT": "application/json",
            "SRSNAME": "EPSG:4326",
            "COUNT": "1000"  # Limita il numero di feature per prestazioni
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

    async def get_map(self, wms_url: str, layer_name: str, bbox: str) -> bytes:
        """Get WMS map image."""
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": layer_name,
            "STYLES": "",
            "CRS": "EPSG:4326",
            "BBOX": bbox,
            "WIDTH": "1024",
            "HEIGHT": "1024",
            "FORMAT": "image/png",
            "TRANSPARENT": "TRUE"
        }

        try:
            async with async_timeout.timeout(10):
                async with self._session.get(wms_url, params=params) as response:
                    response.raise_for_status()
                    return await response.read()
        except Exception as err:
            _LOGGER.error("Error getting WMS map: %s", err)
            raise CannotConnect from err
