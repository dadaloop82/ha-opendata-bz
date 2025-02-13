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
import aiofiles
import xmltodict
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

    def _sanitize_entity_name(self, name: str) -> str:
        """Sanitizza una stringa per uso come nome entità in Home Assistant."""
        name = str(name).lower()

        name = re.sub(r'\([^)]*\)', '', name)

        name = re.sub(r'[^a-z0-9]+', '_', name)

        name = re.sub(r'_+', '_', name)

        name = name.strip('_')
        return name[:64] or 'unnamed'

    def _format_excel_row_label(self, row_idx: int, row_data: dict, columns: list) -> str:
        """Formatta l'etichetta per una riga Excel."""
        # Non mostrare righe con primo valore nan
        first_col = columns[0]
        first_val = row_data.get(first_col, '')
        if pd.isna(first_val):
            return None

        # Prendi solo le prime 5 colonne
        preview_columns = columns[:5]
        data_preview = []
        for col in preview_columns:
            value = str(row_data.get(col, '')).strip()
            if value and pd.notna(value):
                data_preview.append(f"{value}")

        row_num = row_idx + 1
        preview = ' | '.join(data_preview)
        return f"Riga {row_num} - {preview}"

    def _format_excel_column_label(self, col_idx: int, col_name: str, value: str) -> str:
        """Formatta l'etichetta per una colonna Excel."""
        def get_column_letter(n):
            string = ""
            while n >= 0:
                n, remainder = divmod(n, 26)
                string = chr(65 + remainder) + string
                n -= 1
            return string

        col_letter = get_column_letter(col_idx)
        return f"{col_letter} - {col_name}"

    def _clean_resource_name(self, name: str, resource_format: str) -> str:
        name = re.sub(r'\s*\(Formato\s+' + resource_format +
                      r'\)\s*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*\(' + resource_format + r'\)\s*$',
                      '', name, flags=re.IGNORECASE)
        return name.strip()

    async def _fetch_translations(self) -> dict[str, Any]:
        """Fetch translations for current language."""
        current_lang = self._config.get(CONF_LANGUAGE, "en")
        if not self._translations.get(current_lang):
            try:
                component_dir = os.path.dirname(__file__)
                translation_path = os.path.join(
                    component_dir, "translations", f"{current_lang}.json")

                # Usa aiofiles per leggere in modo asincrono
                async with aiofiles.open(translation_path, "r", encoding="utf-8") as file:
                    content = await file.read()
                    translations = json.loads(content)
                    self._translations[current_lang] = translations.get(
                        "config", {})
            except Exception as err:
                _LOGGER.error("Error loading translations: %s", err)
                self._translations[current_lang] = {}
        return self._translations[current_lang]

    @property
    def translations(self) -> Any:
        """
        Proprietà che restituisce le traduzioni in modo asincrono.
        """
        async def _get_translations():
            # Usa il metodo asincrono esistente per recuperare le traduzioni
            return await self._fetch_translations()

        # Restituisci la coroutine da eseguire
        return _get_translations()

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

    def _sort_options(self, options: list[dict]) -> list[dict]:
        """Sort options by label, case-insensitive."""
        return sorted(options, key=lambda x: x['label'].lower())

    def _filter_na_values(self, options: list[dict]) -> list[dict]:
        """Filter out options with N/A values."""
        return [opt for opt in options if 'N/A' not in str(opt.get('label', ''))]

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
            async with aiofiles.open(manifest_path, mode='r') as manifest_file:
                content = await manifest_file.read()
                manifest = json.loads(content)
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
        """Handle resource selection step."""
        errors = {}
        options = []
        supported_resources = []
        unsupported_resources = []
        translations = await self.translations
        try:
            client = OpenDataBolzanoApiClient(self.hass)
            package_id = self._config[CONF_PACKAGE_ID]
            package_details = await client.get_package_details(package_id)
            self._resources = package_details.get("resources", [])
            format_label = translations["resource_labels"]["format"]
            unavailable_label = translations["resource_labels"]["unavailable"]
            for resource in self._resources:
                resource_format = resource.get("format", "").upper()
                resource_name = resource.get("name", resource["id"])
                if resource_name.startswith("Unnamed"):
                    continue
                clean_name = self._clean_resource_name(
                    resource_name, resource_format)
                if resource_format in SUPPORTED_FORMATS:
                    supported_resources.append({
                        "value": resource["id"],
                        "label": format_label.format(
                            format=resource_format,
                            name=clean_name
                        )
                    })
                else:
                    unsupported_resources.append({
                        "value": f"not_available_{resource['id']}",
                        "label": unavailable_label.format(
                            format=resource_format,
                            name=clean_name
                        )
                    })
            supported_resources = self._sort_options(supported_resources)
            unsupported_resources = self._sort_options(
                unsupported_resources)
            options = supported_resources + unsupported_resources
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
                        # Prepare base URL with language
                        parsed = urlparse(resource["url"])
                        query = parse_qs(parsed.query)
                        query.pop("lang", None)
                        lang = self._config.get(CONF_LANGUAGE, "en").lower()
                        query["lang"] = [lang]
                        new_query = urlencode(query, doseq=True)
                        self._current_api_url = urlunparse((
                            parsed.scheme, parsed.netloc, parsed.path,
                            parsed.params, new_query, parsed.fragment
                        ))
                        self._config["resource_url"] = self._current_api_url
                        # Handle different formats
                        if self._config["resource_format"] == "WFS":
                            try:
                                # Assicurati che l'URL WFS sia corretto
                                parsed = urlparse(self._current_api_url)
                                query = parse_qs(parsed.query)
                                typename = resource.get('name', '')
                                _LOGGER.debug("WFS typename: %s", typename)
                                if not typename:
                                    _LOGGER.error("No typename found for WFS")
                                    errors["base"] = "no_wfs_typename"
                                    return
                                # Rimuovi parametri duplicati
                                query.pop('Service', None)
                                query.pop('Request', None)
                                query.pop('VERSION', None)
                                # Aggiungi i parametri corretti
                                query.update({
                                    'SERVICE': ['WFS'],
                                    'VERSION': ['2.0.0'],
                                    'REQUEST': ['GetFeature'],
                                    'OUTPUTFORMAT': ['application/json'],
                                    'TYPENAME': [resource.get('name', '')],
                                    'SRSNAME': ['EPSG:4326']
                                })
                                new_query = urlencode(query, doseq=True)
                                self._current_api_url = urlunparse((
                                    parsed.scheme, parsed.netloc, parsed.path,
                                    parsed.params, new_query, parsed.fragment
                                ))

                                _LOGGER.debug(
                                    "Requesting WFS URL: %s", self._current_api_url)
                                wfs_data = await client.get_resource_data(self._current_api_url)
                                _LOGGER.debug("WFS Response: %s", wfs_data)
                                if isinstance(wfs_data, dict):
                                    features = wfs_data.get("features", [])
                                    if features:
                                        self._rows_data = features
                                        return await self.async_step_confirm()
                                    else:
                                        _LOGGER.error(
                                            "No features found in WFS response")
                                        errors["base"] = "no_wfs_features"
                                else:
                                    _LOGGER.error(
                                        "Invalid WFS response format")
                                    errors["base"] = "invalid_wfs_format"
                            except Exception as error:
                                _LOGGER.exception(
                                    "Error processing WFS data: %s", error)
                                errors["base"] = "wfs_error"

                        elif self._config["resource_format"] in ["JSON", "XLSX", "XLS"]:
                            # Tutti i formati gestiti vanno allo step rows
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
        options = []
        try:
            client = OpenDataBolzanoApiClient(self.hass)
            if self._config.get("resource_format") == "JSON":
                # Fetch JSON data if not already loaded
                if not self._rows_data:
                    json_data = await client.get_resource_data(self._config["resource_url"])
                    if isinstance(json_data, dict) and "rows" in json_data:
                        self._rows_data = json_data["rows"]
                    elif isinstance(json_data, list):
                        self._rows_data = json_data
                    else:
                        self._rows_data = []
                # Create options for JSON rows
                for idx, row in enumerate(self._rows_data):
                    name = row.get("name", f"Row {idx+1}")
                    options.append({
                        "value": f"row_{idx}",
                        "label": name
                    })
            elif self._config.get("resource_format") in ["XLSX", "XLS", "CSV", "XML"]:
                # Fetch Excel data if not already loaded
                if not self._rows_data:
                    data = await client.get_resource_binary(self._config["resource_url"])

                    if self._config.get("resource_format") in ["XLSX", "XLS"]:
                        # Use pandas read_excel with engine specification
                        df = pd.read_excel(io.BytesIO(data), engine='openpyxl')
                        self._rows_data = df.to_dict('records')
                        self._config["xlsx_columns"] = list(df.columns)
                    elif self._config.get("resource_format") == "CSV":
                        _LOGGER.debug("Processing CSV data")
                        try:
                            text_data = data.decode('utf-8')
                            _LOGGER.debug("CSV data preview: %s",
                                          text_data[:200])
                            df = pd.read_csv(io.StringIO(text_data))
                            _LOGGER.debug("CSV columns: %s",
                                          df.columns.tolist())
                            self._rows_data = df.to_dict('records')
                            self._config["xlsx_columns"] = list(df.columns)
                            _LOGGER.debug("Loaded %d rows from CSV",
                                          len(self._rows_data))
                        except Exception as err:
                            _LOGGER.exception("Error processing CSV: %s", err)
                            errors["base"] = "csv_processing_error"
                    elif self._config.get("resource_format") == "XML":
                        # Parsing XML con xmltodict
                        _LOGGER.debug("Processing XML data")
                        xml_dict = xmltodict.parse(data.decode('utf-8'))
                        _LOGGER.debug("XML parsed structure: %s",
                                      json.dumps(xml_dict, indent=2))

                        # Trova la lista principale
                        found_list = None
                        if 'root' in xml_dict and 'item' in xml_dict['root']:
                            _LOGGER.debug(
                                "Found standard XML structure with root/item")
                            found_list = xml_dict['root']['item']
                        else:
                            _LOGGER.debug("Searching for deepest list in XML")
                            found_list = find_list(xml_dict)

                        if found_list:
                            _LOGGER.debug(
                                "Found list with %d items", len(found_list))
                            self._rows_data = found_list
                            if self._rows_data:
                                self._config["xlsx_columns"] = list(
                                    self._rows_data[0].keys())
                                _LOGGER.debug(
                                    "Extracted columns: %s", self._config["xlsx_columns"])
                        else:
                            _LOGGER.error("No suitable list found in XML")
                            errors["base"] = "invalid_xml_format"
                    else:
                        df = pd.read_excel(io.BytesIO(data))
                        self._rows_data = df.to_dict('records')
                        self._config["xlsx_columns"] = list(df.columns)
            # Gestione selezione e avanzamento

            # Create options from the loaded data
            for idx, row in enumerate(self._rows_data):
                # For Excel/CSV, use first column as name if available
                if self._config.get("resource_format") in ["XLSX", "XLS", "CSV"]:
                    name = self._format_excel_row_label(
                        idx, row, self._config["xlsx_columns"])
                else:
                    name = str(row.get("name", f"Row {idx+1}"))

                options.append({
                    "value": f"row_{idx}",
                    "label": name
                })

            # Sort options
            options = self._sort_options(options)
            options = self._filter_na_values(options)

            if user_input is not None:
                selected_row = user_input.get("row")
                if selected_row:
                    selected_index = int(selected_row.split("_")[1])
                    self._config["selected_rows"] = [selected_index]
                    return await self.async_step_fields()
                else:
                    errors["base"] = "no_rows_selected"
        except Exception as error:
            _LOGGER.exception("Unexpected exception in rows step: %s", error)
            errors["base"] = "unknown"
        return self.async_show_form(
            step_id="rows",
            data_schema=vol.Schema({
                vol.Required("row"): vol.In({opt["value"]: opt["label"] for opt in options})
            }),
            errors=errors if errors else None,
            description_placeholders={"api_url": self._api_url_link()}
        )

    async def async_step_fields(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle field selection step."""
        errors = {}
        options = []
        processed_fields = set()
        try:
            # Determina le colonne in base al formato
            if self._config.get("resource_format") in ["XLSX", "XLS"]:
                columns = self._config.get("xlsx_columns", [])
            else:  # JSON
                # Per JSON, considera le chiavi della riga selezionata come colonne
                selected_row = self._rows_data[self._config["selected_rows"][0]]
                columns = list(selected_row.keys())
            selected_row = self._rows_data[self._config["selected_rows"][0]]
            # Logica comune per generazione delle opzioni
            if self._config.get("resource_format") in ["XLSX", "XLS"]:
                for col_idx, column in enumerate(columns):
                    if not column.startswith("Unnamed"):
                        value = selected_row.get(column, "")
                        if pd.notna(value):
                            formatted_label = self._format_excel_column_label(
                                col_idx, column)
                            options.append({
                                "value": f"field:{column}",
                                "label": f"{formatted_label}: {value}"
                            })
            else:  # JSON
                # Process measurement fields if available
                measurements = selected_row.get("measurements", [])
                if isinstance(measurements, list):
                    for measurement in measurements:
                        if "description" in measurement and "code" in measurement:
                            code = measurement["code"].lower()
                            description = measurement["description"]
                            value = selected_row.get(code, "N/A")
                            options.append({
                                "value": f"measurement:{code}",
                                "label": f"{code} ({description}): {value}"
                            })
                    options = self._sort_options(options)
                    options = self._filter_na_values(options)
                    processed_fields.add(code)
                # Process regular fields not already handled as measurements
                for field_name, field_value in selected_row.items():
                    if (field_name != "measurements" and
                            field_name.lower() not in processed_fields and
                            not isinstance(field_value, (dict, list))):
                        options.append({
                            "value": f"field:{field_name}",
                            "label": f"{field_name}: {field_value}"
                        })
            if user_input is not None:
                selected = user_input.get("fields", [])
                if not selected:
                    errors["base"] = "no_fields_selected"
                else:
                    selected_fields = []
                    for item in selected:
                        try:
                            field_type, key = item.split(":", 1)
                            selected_fields.append((field_type, key))
                        except Exception:
                            pass
                    if selected_fields:
                        self._config["selected_fields"] = selected_fields
                        # Calcola il numero totale di sensori che verranno creati
                        total_sensors_count = len(selected_fields)
                        if total_sensors_count > 100:
                            # Mostra un avviso se verranno creati troppi sensori
                            errors["base"] = "too_many_sensors"
                        else:
                            return await self.async_step_confirm()
        except Exception as error:
            _LOGGER.exception("Unexpected exception in fields step: %s", error)
            errors["base"] = "unknown"
        title = "Seleziona Colonna" if self._config.get("resource_format") in [
            "XLSX", "XLS"] else "Seleziona Campo"
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
            wfs_features = self._rows_data[:500]
            total_features = len(wfs_features)

            if total_features == 0:
                errors = {"base": "no_wfs_features"}
                return self.async_show_form(
                    step_id="confirm",
                    data_schema=vol.Schema({}),
                    errors=errors,
                    description_placeholders={
                        "api_url": self._api_url_link(),
                        "fields_preview": "Nessun dato geografico rilevato nel servizio WFS"
                    }
                )

            if total_features > 500:
                preview_text = f"Trovate {total_features} features. Verranno utilizzate solo le prime 500 features per limitare il carico di sistema."
            else:
                preview_text = f"Verranno creati {total_features} sensori WFS"

            if total_features > 100:
                errors = {"base": "too_many_sensors"}
                return self.async_show_form(
                    step_id="confirm",
                    data_schema=vol.Schema({}),
                    errors=errors,
                    description_placeholders={
                        "api_url": self._api_url_link(),
                        "fields_preview": f"Troppi dati: {total_features} features rilevate"
                    }
                )

            preview_text = f"Verranno creati {total_features} sensori WFS"
        elif self._config.get("resource_format", "").upper() in ["XLSX", "XLS"]:
            try:
                selected_row = self._rows_data[self._config["selected_rows"][0]]
                selected_fields = self._config["selected_fields"]
                translations = await self._fetch_translations()
                preview_format = translations.get("step", {}).get("confirm", {}).get(
                    "previews", {}).get("entity", "{entity_id}: {value}")
                preview_text = []
                base_name = str(selected_row.get(
                    list(selected_row.keys())[0], ''))
                clean_base_name = re.sub(
                    r'[^a-z0-9_]+', '_', base_name.lower().strip())
                for field_type, column in selected_fields:
                    value = selected_row.get(column, "N/A")
                    clean_base_name = self._sanitize_entity_name(base_name)
                    clean_column = self._sanitize_entity_name(column)
                    entity_id = f"sensor.provbz_{clean_base_name}_{clean_column}"
                    preview_text.append(preview_format.format(
                        entity_id=entity_id, value=value))
                preview_text = "\n".join(preview_text)
            except Exception as err:
                _LOGGER.error("Error creating preview: %s", err)
                preview_text = await self.translations["previews"]["error"]
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
                        sensor_field = self._sanitize_entity_name(key.lower())
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
