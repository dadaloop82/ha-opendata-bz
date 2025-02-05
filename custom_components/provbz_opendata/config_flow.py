"""
Config Flow for OpenData Alto Adige Integration.
This module handles the configuration flow for the OpenData Hub integration of the
Autonomous Province of Bolzano/Bozen. It provides a step-by-step wizard for setting up
data sources and sensors in Home Assistant.
Project: ha-opendata-bz (https://github.com/dadaloop82/ha-opendata-bz)
Author: Daniel Stimpfl (@dadaloop82)
License: Apache License 2.0
"""
from __future__ import annotations
import logging
import re
from typing import Any
import voluptuous as vol
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import pandas as pd
import io
import os
import json
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import selector
from .const import (
    DOMAIN,
    NAME,
    CONF_GROUP_ID,
    CONF_PACKAGE_ID,
    CONF_RESOURCE_ID,
    CONF_LANGUAGE,
    SUPPORTED_LANGUAGES,
    GROUP_TRANSLATIONS,
    BASE_API_URL,
)
from .api import OpenDataBolzanoApiClient, CannotConnect
from .const import SUPPORTED_FORMATS
_LOGGER = logging.getLogger(__name__)


class ProvbzOpendataConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configuration flow handler for OpenData Alto Adige integration.
    This class manages the step-by-step configuration process including:
    1. Language selection
    2. Data group selection
    3. Package selection within group
    4. Resource selection (JSON/WFS)
    5. Data point selection for JSON resources
    6. Field selection for JSON resources
    7. Final confirmation
    """
    VERSION = 1
    STEPS = ["user", "language", "group", "package",
             "resource", "rows", "fields", "confirm"]

    def __init__(self) -> None:
        """Initialize the configuration flow.
        Sets up the initial state variables for tracking progress through
        the configuration steps.
        """
        self._config: dict[str, Any] = {}          # Configuration data
        self._groups: list[dict[str, Any]] = []    # Available data groups
        self._packages: list[dict[str, Any]] = []  # Available packages
        self._resources: list[dict[str, Any]] = []  # Available resources
        # Data rows for JSON resources
        self._rows_data: list[dict[str, Any]] = []
        self._current_api_url: str = BASE_API_URL  # Current API endpoint
        self._current_step: int = 0                # Current step in the flow
        self._translations: dict[str, Any] = {}

    @property
    def translations(self) -> dict[str, Any]:
        """Get translations for current language."""
        current_lang = self._config.get(CONF_LANGUAGE, "en")
        if not self._translations.get(current_lang):
            try:
                component_dir = os.path.dirname(__file__)
                translation_path = os.path.join(
                    component_dir, "translations", f"{current_lang}.json")
                if os.path.exists(translation_path):
                    with open(translation_path, "r", encoding="utf-8") as file:
                        self._translations[current_lang] = json.load(
                            file).get("config", {})
                else:
                    fallback_path = os.path.join(
                        component_dir, "translations", "en.json")
                    if os.path.exists(fallback_path):
                        with open(fallback_path, "r", encoding="utf-8") as file:
                            self._translations[current_lang] = json.load(
                                file).get("config", {})
                    else:
                        _LOGGER.warning(
                            "No translation file found for language %s and no fallback available",
                            current_lang
                        )
                        self._translations[current_lang] = {}
            except Exception as err:
                _LOGGER.error("Error loading translations: %s", err)
                self._translations[current_lang] = {}
        return self._translations[current_lang]

    @property
    def _api_url(self) -> str:
        """Generate API URL with forced language parameter.
        Returns:
            str: API URL with the correct language parameter
        """
        parsed = urlparse(self._current_api_url)
        query = parse_qs(parsed.query)
        lang = self._config.get(CONF_LANGUAGE, "en").lower()
        query["lang"] = [lang]
        new_query = urlencode(query, doseq=True)
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))

    def _api_url_link(self) -> str:
        """Generate HTML link for API URL preview.
        Returns:
            str: HTML anchor tag with API URL
        """
        return f'<a href="{self._current_api_url}" target="_blank">{self._current_api_url}</a>'

    async def async_step(self, step_id: str, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a step in the configuration flow.
        Args:
            step_id: Identifier of the step to handle
            user_input: User provided input data
        Returns:
            FlowResult: Next step in the configuration flow
        """
        if step_id not in self.STEPS:
            return self.async_abort(reason="unknown_step")
        self._current_step = self.STEPS.index(step_id)
        method = f"async_step_{step_id}"
        return await getattr(self, method)(user_input)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step.
        Sets default name and moves to language selection.
        """
        self._config[CONF_NAME] = NAME
        return await self.async_step_language()

    async def async_step_language(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle language selection step."""
        if user_input is not None:
            self._config.update(user_input)
            return await self.async_step_group()
        supported_types = ", ".join(SUPPORTED_FORMATS.values())
        try:
            manifest_path = os.path.join(
                os.path.dirname(__file__), "manifest.json")
            with open(manifest_path) as manifest_file:
                manifest = json.load(manifest_file)
                version = manifest.get("version", "?.?.?")
        except Exception as err:
            _LOGGER.error("Error reading manifest version: %s", err)
            version = "?.?.?"
        return self.async_show_form(
            step_id="language",
            data_schema=vol.Schema({
                vol.Required(CONF_LANGUAGE): vol.In(SUPPORTED_LANGUAGES)
            }),
            description_placeholders={
                "supported_types": supported_types,
                "version": version
            }
        )

    async def async_step_group(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle group selection step.
        Fetches and displays available data groups from the API.
        """
        errors = {}
        groups = {}
        try:
            client = OpenDataBolzanoApiClient(self.hass)
            self._groups = await client.get_groups()
            lang = self._config.get(CONF_LANGUAGE, "en")
            # Create group options with translations
            groups = {
                group["name"]: GROUP_TRANSLATIONS[lang].get(
                    group["name"], group["name"])
                for group in self._groups
            }
            if user_input is not None:
                self._config.update(user_input)
                self._current_api_url = (
                    f"{BASE_API_URL}/group_show"
                    f"?id={user_input[CONF_GROUP_ID]}"
                    f"&include_datasets=true"
                )
                return await self.async_step_package()
        except CannotConnect:
            _LOGGER.exception("Connection failed")
            errors["base"] = "cannot_connect"
        except Exception as error:
            _LOGGER.exception("Unexpected exception: %s", error)
            errors["base"] = "unknown"
        return self.async_show_form(
            step_id="group",
            data_schema=vol.Schema({
                vol.Required(CONF_GROUP_ID): vol.In(
                    groups or {"default": self.hass.data[DOMAIN].get(
                        "loading_errors", {}).get("default_groups")}
                )
            }),
            errors=errors
        )

    async def async_step_package(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle package selection step.
        Fetches and displays available packages within selected group.
        """
        errors = {}
        packages = {}
        try:
            client = OpenDataBolzanoApiClient(self.hass)
            group_id = self._config[CONF_GROUP_ID]
            self._packages = await client.get_group_packages(group_id)
            if not self._packages:
                errors["base"] = "no_packages"
            else:
                packages = {
                    package["id"]: package.get(
                        "title", package.get("name", package["id"]))
                    for package in self._packages
                }
            if user_input is not None and not errors:
                self._config.update(user_input)
                self._current_api_url = (
                    f"{BASE_API_URL}/package_show"
                    f"?id={user_input[CONF_PACKAGE_ID]}"
                )
                return await self.async_step_resource()
        except CannotConnect:
            _LOGGER.exception("Connection failed")
            errors["base"] = "cannot_connect"
        except Exception as error:
            _LOGGER.exception("Unexpected exception: %s", error)
            errors["base"] = "unknown"
        return self.async_show_form(
            step_id="package",
            data_schema=vol.Schema({
                vol.Required(CONF_PACKAGE_ID): vol.In(
                    packages or {"default": self.hass.data[DOMAIN].get(
                        "loading_errors", {}).get("default_packages")}
                )
            }),
            errors=errors,
            description_placeholders={"api_url": self._api_url_link()}
        )

    async def async_step_resource(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle resource selection step.
        Displays available data resources and their formats (JSON/WFS).
        Handles different configuration paths based on selected format.
        """
        errors = {}
        options = []
        try:
            client = OpenDataBolzanoApiClient(self.hass)
            package_id = self._config[CONF_PACKAGE_ID]
            package_details = await client.get_package_details(package_id)
            self._resources = package_details.get("resources", [])
            format_label = self.translations["resource_labels"]["format"]
            unavailable_label = self.translations["resource_labels"]["unavailable"]
            for resource in self._resources:
                resource_format = resource.get("format", "").upper()
                resource_name = resource.get("name", resource["id"])
                clean_name = re.sub(r"\s*\(Formato [^)]+\)", "", resource_name)
                if resource_format in SUPPORTED_FORMATS:
                    options.append({
                        "value": resource["id"],
                        "label": format_label.format(
                            format=resource_format,
                            name=clean_name
                        )
                    })
                else:
                    options.append({
                        "value": f"not_available_{resource['id']}",
                        "label": unavailable_label.format(
                            format=resource_format,
                            name=clean_name
                        )
                    })
            if user_input is not None:
                selected_resource_id = user_input.get(CONF_RESOURCE_ID)
                if not selected_resource_id.startswith("not_available_"):
                    self._config[CONF_RESOURCE_ID] = selected_resource_id
                    resource = next(
                        (r for r in self._resources if r["id"]
                         == selected_resource_id),
                        None
                    )
                    if resource and resource.get("url"):
                        # Set resource format and prepare URL
                        self._config["resource_format"] = resource.get(
                            "format", "").upper()
                        parsed = urlparse(resource["url"])
                        query = parse_qs(parsed.query)
                        query.pop("lang", None)
                        lang = self._config.get(CONF_LANGUAGE, "en").lower()
                        query["lang"] = [lang]
                        # Add WFS specific parameters if needed
                        if self._config["resource_format"] == "WFS":
                            query.update({
                                "SERVICE": ["WFS"],
                                "VERSION": ["2.0.0"],
                                "REQUEST": ["GetFeature"],
                                "OUTPUTFORMAT": ["application/json"],
                                "TYPENAME": [resource.get("name", "")],
                                "SRSNAME": ["EPSG:4326"]
                            })
                        # Build final URL
                        new_query = urlencode(query, doseq=True)
                        self._current_api_url = urlunparse((
                            parsed.scheme,
                            parsed.netloc,
                            parsed.path,
                            parsed.params,
                            new_query,
                            parsed.fragment
                        ))
                        self._config["resource_url"] = self._current_api_url
                        # Choose next step based on format
                        if self._config["resource_format"] == "WFS":
                            return await self.async_step_confirm()
                        elif self._config["resource_format"] in ["XLSX", "XLS"]:
                            try:
                                # Fetch XLSX data preview
                                xlsx_data = await client.get_resource_binary(self._config["resource_url"])
                                df = pd.read_excel(io.BytesIO(xlsx_data))
                                # Store preview data
                                self._rows_data = df.to_dict('records')
                                # Store column information for later
                                self._config["xlsx_columns"] = list(df.columns)
                                # Instead of going directly to confirm, go to rows selection
                                return await self.async_step_rows()
                            except Exception as err:
                                _LOGGER.error(
                                    "Error processing XLSX file: %s", err)
                                errors["base"] = "invalid_xlsx"
                        # Default to JSON flow
                        return await self.async_step_rows()
        except CannotConnect:
            _LOGGER.exception("Connection failed")
            errors["base"] = "cannot_connect"
        except Exception as error:
            _LOGGER.exception("Unexpected exception: %s", error)
            errors["base"] = "unknown"
        return self.async_show_form(
            step_id="resource",
            data_schema=vol.Schema({
                vol.Required(CONF_RESOURCE_ID): selector({
                    "select": {
                        "options": options,
                        "mode": "list"
                    }
                })
            }),
            errors=errors,
            description_placeholders={"api_url": self._api_url_link()}
        )

    async def async_step_rows(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle row selection step for both JSON and Excel resources."""
        errors = {}
        row_names = {}
        try:
            if self._config.get("resource_format") in ["XLSX", "XLS"]:
                column_format = self.translations["step"]["rows"]["labels"]["column_value"]
                row_format = self.translations["step"]["rows"]["labels"]["row_format"]
                for idx, row in enumerate(self._rows_data):
                    preview_values = []
                    for col in self._config["xlsx_columns"]:
                        val = row.get(col, "")
                        preview_values.append(
                            column_format.format(column=col, value=val))
                    preview = " | ".join(preview_values)
                    row_names[f"row_{idx}"] = row_format.format(
                        number=idx+1, preview=preview)
                if user_input is not None:
                    selected_row = user_input.get("row")
                    if selected_row:
                        selected_index = int(selected_row.split("_")[1])
                        self._config["selected_rows"] = [selected_index]
                        return await self.async_step_fields()
                    else:
                        errors["base"] = "no_rows_selected"
            else:
                client = OpenDataBolzanoApiClient(self.hass)
                resource = next(
                    (r for r in self._resources if r["id"]
                     == self._config[CONF_RESOURCE_ID]),
                    None
                )
                if resource and resource.get("url"):
                    # Prepare URL with language parameter
                    parsed = urlparse(resource["url"])
                    query = parse_qs(parsed.query)
                    query.pop("lang", None)
                    lang = self._config.get(CONF_LANGUAGE, "en").lower()
                    query["lang"] = [lang]
                    new_query = urlencode(query, doseq=True)
                    new_url = urlunparse((
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        parsed.params,
                        new_query,
                        parsed.fragment
                    ))
                    # Fetch and process data
                    json_data = await client.get_resource_data(new_url)
                    if isinstance(json_data, dict) and "rows" in json_data:
                        self._rows_data = json_data["rows"]
                    elif isinstance(json_data, list):
                        self._rows_data = json_data
                    else:
                        self._rows_data = []
                    # Prepare row options
                    row_names = {
                        (row.get("name") or f"row_{idx}"): (row.get("name") or f"row_{idx}")
                        for idx, row in enumerate(self._rows_data)
                    }
                    # Handle user selection
                    if user_input is not None:
                        selected_row = user_input.get("row")
                        if selected_row:
                            selected_index = next(
                                (idx for idx, row in enumerate(self._rows_data)
                                 if (row.get("name") or f"row_{idx}") == selected_row),
                                None
                            )
                            if selected_index is not None:
                                self._config["selected_rows"] = [
                                    selected_index]
                                return await self.async_step_fields()
                            else:
                                errors["base"] = "no_rows_selected"
                        else:
                            errors["base"] = "no_rows_selected"
        except CannotConnect:
            _LOGGER.exception("Connection failed")
            errors["base"] = "cannot_connect"
        except Exception as error:
            _LOGGER.exception(
                "Unexpected exception in rows step: %s", error)
            errors["base"] = "unknown"
        options = [
            {"value": f"row_{idx}",
             # Rimuoviamo il testo "Riga" hardcoded
             "label": f"{row.get(list(row.keys())[0], '')} | {', '.join(f'{k}: {v}' for k,v in row.items())}"
             } for idx, row in enumerate(self._rows_data)
        ]
        return self.async_show_form(
            step_id="rows",
            data_schema=vol.Schema({
                vol.Required("row"): selector({
                    "select": {
                        "options": options,
                        "mode": "list",
                        "variant": "list"
                    }
                })
            }),
            errors=errors if errors else None,
            description_placeholders={"api_url": self._api_url_link()}
        )

    async def async_step_fields(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle field selection step for both JSON and Excel resources."""
        errors = {}
        options = []
        try:
            if self._config.get("resource_format") in ["XLSX", "XLS"]:
                # Excel handling
                selected_row = self._rows_data[self._config["selected_rows"][0]]
                # Create options for each column with its value
                for column in self._config["xlsx_columns"]:
                    value = selected_row.get(column, "N/A")
                    options.append({
                        "value": f"field:{column}",
                        "label": f"{column}: {value}"
                    })
                # Handle user selection
                if user_input is not None:
                    selected = user_input.get("fields", [])
                    selected_fields = []
                    for item in selected:
                        try:
                            field_type, key = item.split(":", 1)
                            selected_fields.append((field_type, key))
                        except Exception:
                            pass
                    if selected_fields:
                        self._config["selected_fields"] = selected_fields
                        return await self.async_step_confirm()
                    else:
                        errors["base"] = "no_fields_selected"
            else:
                # Get the first row or selected row
                if "selected_rows" not in self._config or not self._config["selected_rows"]:
                    first_row = self._rows_data[0]
                else:
                    first_row = self._rows_data[self._config["selected_rows"][0]]
                processed_fields = set()
                # Process measurement fields if available
                measurements = first_row.get("measurements", [])
                if isinstance(measurements, list):
                    for measurement in measurements:
                        if "description" in measurement and "code" in measurement:
                            code = measurement["code"].lower()
                            description = measurement["description"]
                            value = first_row.get(code, "N/A")
                            label = (f"{code} ({description}): {value}"
                                     if value != "N/A"
                                     else f"{code}: {value}")
                            options.append({
                                "value": f"measurement:{code}",
                                "label": label
                            })
                            processed_fields.add(code)
                # Process regular fields not already handled as measurements
                for field_name, field_value in first_row.items():
                    if (field_name != "measurements" and
                            field_name.lower() not in processed_fields):
                        options.append({
                            "value": f"field:{field_name}",
                            "label": f"{field_name}: {field_value}"
                        })
                # Handle user selection
                if user_input is not None:
                    selected = user_input.get("fields", [])
                    selected_fields = []
                    for item in selected:
                        try:
                            field_type, key = item.split(":", 1)
                            selected_fields.append((field_type, key))
                        except Exception:
                            pass
                    if selected_fields:
                        self._config["selected_fields"] = selected_fields
                        return await self.async_step_confirm()
                    else:
                        errors["base"] = "no_fields_selected"
        except Exception as error:
            _LOGGER.exception("Unexpected exception in fields step: %s", error)
            errors["base"] = "unknown"
        return self.async_show_form(
            step_id="fields",
            data_schema=vol.Schema({
                vol.Required("fields", default=[]): selector({
                    "select": {
                        "multiple": True,
                        "options": options,
                        "mode": "dropdown"
                    }
                })
            }),
            errors=errors if errors else None,
            description_placeholders={"api_url": self._api_url_link()}
        )

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle final confirmation step.
        Shows preview of entities to be created and finalizes configuration.
        Handles both JSON and WFS resources appropriately.
        """
        if user_input is not None:
            # Initialize configuration storage
            self.hass.data.setdefault(DOMAIN, {})
            # Prepare final configuration data
            config_data = dict(self._config)
            config_data["rows_data"] = self._rows_data
            config_data["resources"] = self._resources
            config_data["unique_id"] = self.flow_id
            # Get selected resource details
            resource = next(
                (r for r in self._resources if r["id"]
                 == self._config[CONF_RESOURCE_ID]),
                None
            )
            # Store configuration in Home Assistant
            self.hass.data[DOMAIN][self.flow_id] = {
                "api": OpenDataBolzanoApiClient(self.hass),
                "config": config_data,
                "rows_data": self._rows_data,
                "resources": self._resources
            }
            # Create configuration entry
            return self.async_create_entry(
                title=resource.get("name", NAME),
                data=config_data
            )
        # Prepare preview based on resource type
        if self._config.get("resource_format", "").upper() == "WFS":
            preview_text = self.translations["step"]["confirm"]["previews"]["wfs"]
        elif self._config.get("resource_format", "").upper() in ["XLSX", "XLS"]:
            try:
                selected_row = self._rows_data[self._config["selected_rows"][0]]
                selected_fields = self._config["selected_fields"]
                preview_format = self.translations["step"]["confirm"]["previews"]["entity"]
                preview_text = []
                base_name = str(selected_row.get(
                    list(selected_row.keys())[0], ''))
                clean_base_name = re.sub(
                    r'[^a-z0-9_]+', '_', base_name.lower().strip())
                for field_type, column in selected_fields:
                    value = selected_row.get(column, "N/A")
                    clean_column = re.sub(
                        r'[^a-z0-9_]+', '_', column.lower().strip())
                    entity_id = f"sensor.provbz_xlsx_{clean_base_name}_{clean_column}"
                    preview_text.append(preview_format.format(
                        entity_id=entity_id, value=value))
                preview_text = "\n".join(preview_text)
            except Exception as err:
                _LOGGER.error("Error creating preview: %s", err)
                preview_text = self.translations["previews"]["error"]
        else:
            # Generate preview for JSON sensors
            sensor_previews = []
            for row in [self._rows_data[idx] for idx in self._config.get("selected_rows", [])]:
                row_name = row.get("name", "row")
                row_name_clean = re.sub(
                    r'[^a-z0-9_]+', '_', row_name.lower().strip())
                for field_type, key in self._config["selected_fields"]:
                    if field_type == "measurement":
                        measurement = next(
                            (m for m in row.get("measurements", [])
                             if m.get("code", "").lower() == key.lower()),
                            None
                        )
                        if measurement and "description" in measurement:
                            sensor_field = (f"{key} ({measurement.get('description', key)})"
                                            .lower().replace(" ", "_"))
                        else:
                            sensor_field = key.lower()
                    else:
                        sensor_field = key.lower()
                    sensor_field = re.sub(r'_+', '_', sensor_field).strip('_')
                    entity_id = f"sensor.provbz_{row_name_clean}_{sensor_field}"
                    value = row.get(key, "N/A")
                    sensor_previews.append(f"{entity_id}: {value}")
            preview_text = "\n".join(sensor_previews)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "api_url": self._api_url_link(),
                "fields_preview": preview_text
            }
        )
