"""Config flow for OpenData Provincia Bolzano integration."""
from __future__ import annotations

import logging
import re
from typing import Any
import voluptuous as vol
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

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

_LOGGER = logging.getLogger(__name__)


class OpenDataProvinceBolzanoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenData Provincia Bolzano integration."""

    VERSION = 1
    STEPS = ["user", "language", "group", "package",
             "resource", "rows", "fields", "confirm"]

    def __init__(self) -> None:
        """Initialize flow."""
        self._config: dict[str, Any] = {}
        self._groups: list[dict[str, Any]] = []
        self._packages: list[dict[str, Any]] = []
        self._resources: list[dict[str, Any]] = []
        self._rows_data: list[dict[str, Any]] = []
        self._current_api_url: str = BASE_API_URL
        self._current_step: int = 0

    @property
    def _api_url(self) -> str:
        """Return current API URL with forced language parameter."""
        parsed = urlparse(self._current_api_url)
        query = parse_qs(parsed.query)
        # Forza la lingua scelta dall'utente
        lang = self._config.get(CONF_LANGUAGE, "en").lower()
        query["lang"] = [lang]
        new_query = urlencode(query, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    def _api_url_link(self) -> str:
        """Return a clickable HTML link for the current API URL."""
        # Nota: qui viene usato self._current_api_url non _api_url per mantenere il link originale;
        # puoi modificarlo se vuoi visualizzare l'URL con lang forzato.
        return f'<a href="{self._current_api_url}" target="_blank">{self._current_api_url}</a>'

    async def async_step(self, step_id: str, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a step."""
        if step_id not in self.STEPS:
            return self.async_abort(reason="unknown_step")
        self._current_step = self.STEPS.index(step_id)
        method = f"async_step_{step_id}"
        return await getattr(self, method)(user_input)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        # Imposta direttamente il nome predefinito
        self._config[CONF_NAME] = NAME
        # Vai direttamente al prossimo step (language)
        return await self.async_step_language()

    async def async_step_language(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle language selection."""
        if user_input is not None:
            self._config.update(user_input)
            return await self.async_step_group()
        return self.async_show_form(
            step_id="language",
            data_schema=vol.Schema({
                vol.Required(CONF_LANGUAGE): vol.In(SUPPORTED_LANGUAGES)
            })
        )

    async def async_step_group(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the group selection step."""
        errors = {}
        groups = {}
        try:
            client = OpenDataBolzanoApiClient(self.hass)
            self._groups = await client.get_groups()
            lang = self._config.get(CONF_LANGUAGE, "en")
            groups = {
                group["name"]: GROUP_TRANSLATIONS[lang].get(
                    group["name"], group["name"])
                for group in self._groups
            }
            if user_input is not None:
                self._config.update(user_input)
                # Aggiunge il parametro include_datasets=true per ottenere i dataset
                self._current_api_url = f"{BASE_API_URL}/group_show?id={user_input[CONF_GROUP_ID]}&include_datasets=true"
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
                vol.Required(CONF_GROUP_ID): vol.In(groups or {"default": "Error loading groups"})
            }),
            errors=errors
        )

    async def async_step_package(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the package selection step."""
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
                self._current_api_url = f"{BASE_API_URL}/package_show?id={user_input[CONF_PACKAGE_ID]}"
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
                vol.Required(CONF_PACKAGE_ID): vol.In(packages or {"default": "Error loading packages"})
            }),
            errors=errors,
            description_placeholders={"api_url": self._api_url_link()}
        )

    async def async_step_resource(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the resource selection step."""
        errors = {}
        options = []
        try:
            client = OpenDataBolzanoApiClient(self.hass)
            package_id = self._config[CONF_PACKAGE_ID]
            package_details = await client.get_package_details(package_id)
            self._resources = package_details.get("resources", [])

            # Aggiungi prima le risorse selezionabili: JSON e WMS.
            for resource in self._resources:
                resource_format = resource.get("format", "").upper()
                if resource_format in ["JSON", "WFS"]:
                    resource_name = resource.get("name", resource["id"])
                    clean_name = re.sub(
                        r"\s*\(Formato [^)]+\)", "", resource_name)
                    options.append({
                        "value": resource["id"],
                        "label": f"[{resource_format}] {clean_name}"
                    })

            # Aggiungi le altre risorse (non selezionabili).
            for resource in self._resources:
                resource_format = resource.get("format", "").upper()
                if resource_format not in ["JSON", "WFS"]:
                    resource_name = resource.get("name", resource["id"])
                    clean_name = re.sub(
                        r"\s*\(Formato [^)]+\)", "", resource_name)
                    options.append({
                        "value": f"not_available_{resource['id']}",
                        "label": f"🚫 [{resource_format}] {clean_name}"
                    })

            if user_input is not None:
                selected_resource_id = user_input.get(CONF_RESOURCE_ID)
                if not selected_resource_id.startswith("not_available_"):
                    self._config[CONF_RESOURCE_ID] = selected_resource_id
                    resource = next(
                        (r for r in self._resources if r["id"] == selected_resource_id), None)
                    if resource and resource.get("url"):
                        self._config["resource_format"] = resource.get(
                            "format", "").upper()
                        # Costruisci l'URL forzando il parametro lang
                        parsed = urlparse(resource["url"])
                        query = parse_qs(parsed.query)
                        query.pop("lang", None)
                        lang = self._config.get(CONF_LANGUAGE, "en").lower()
                        query["lang"] = [lang]
                        if self._config["resource_format"] == "WFS":
                            query.update({
                            "SERVICE": ["WFS"],
                            "VERSION": ["2.0.0"],
                            "REQUEST": ["GetFeature"],
                            "OUTPUTFORMAT": ["application/json"],
                            "TYPENAME": [resource.get("name", "")],
                            "SRSNAME": ["EPSG:4326"]
                        })
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
                        # Se il formato è WMS, salta lo step rows
                        if self._config["resource_format"] == "WFS":
                            return await self.async_step_confirm()
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
        """Handle the rows selection step."""
        errors = {}
        row_names = {}
        try:
            client = OpenDataBolzanoApiClient(self.hass)
            resource = next(
                (r for r in self._resources if r["id"] == self._config[CONF_RESOURCE_ID]), None)
            if resource and resource.get("url"):
                parsed = urlparse(resource["url"])
                query = parse_qs(parsed.query)
                query.pop("lang", None)
                lang = self._config.get(CONF_LANGUAGE, "en").lower()
                query["lang"] = [lang]
                new_query = urlencode(query, doseq=True)
                new_url = urlunparse(
                    (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
                json_data = await client.get_resource_data(new_url)
                if isinstance(json_data, dict) and "rows" in json_data:
                    self._rows_data = json_data["rows"]
                elif isinstance(json_data, list):
                    self._rows_data = json_data
                else:
                    self._rows_data = []
                row_names = {
                    (row.get("name") or f"row_{idx}"): (row.get("name") or f"row_{idx}")
                    for idx, row in enumerate(self._rows_data)
                }
                if user_input is not None:
                    selected_row = user_input.get("row")
                    if selected_row:
                        selected_index = next(
                            (idx for idx, row in enumerate(self._rows_data)
                             if (row.get("name") or f"row_{idx}") == selected_row),
                            None
                        )
                        if selected_index is not None:
                            self._config["selected_rows"] = [selected_index]
                            return await self.async_step_fields()
                        else:
                            errors["base"] = "no_rows_selected"
                    else:
                        errors["base"] = "no_rows_selected"
        except CannotConnect:
            _LOGGER.exception("Connection failed")
            errors["base"] = "cannot_connect"
        except Exception as error:
            _LOGGER.exception("Unexpected exception in rows step: %s", error)
            errors["base"] = "unknown"
        return self.async_show_form(
            step_id="rows",
            data_schema=vol.Schema({vol.Required("row"): vol.In(row_names)}),
            errors=errors if errors else None,
            last_step=False,
            description_placeholders={"api_url": self._api_url_link()}
        )

    async def async_step_fields(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the fields selection step."""
        errors = {}
        options = []
        try:
            if "selected_rows" not in self._config or not self._config["selected_rows"]:
                first_row = self._rows_data[0]
            else:
                first_row = self._rows_data[self._config["selected_rows"][0]]
            processed_fields = set()
            # Opzioni per i campi di measurements
            measurements = first_row.get("measurements", [])
            if isinstance(measurements, list):
                for measurement in measurements:
                    if "description" in measurement and "code" in measurement:
                        code = measurement["code"].lower()
                        description = measurement["description"]
                        value = first_row.get(code, "N/A")
                        if value == "N/A":
                            label = f"{code}: {value}"
                        else:
                            label = f"{code} ({description}): {value}"
                        options.append({
                            "value": f"measurement:{code}",
                            "label": label
                        })
                        processed_fields.add(code)
            # Opzioni per i campi normali (solo se non già processati in measurements)
            for field_name, field_value in first_row.items():
                if field_name == "measurements":
                    continue
                if field_name.lower() in processed_fields:
                    continue
                options.append({
                    "value": f"field:{field_name}",
                    "label": f"{field_name}: {field_value}"
                })
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
            errors=errors if errors else None,  # Rimuovi l'errore di default
            description_placeholders={"api_url": self._api_url_link()}
        )

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """
        Show the confirmation dialog.
        Se il layer selezionato è WMS, viene mostrato un preview specifico;
        altrimenti, viene costruito il preview basato sui campi selezionati.
        I testi fissi devono essere gestiti tramite i file di traduzione.
        """
        if user_input is not None:
            self.hass.data.setdefault(DOMAIN, {})
            config_data = dict(self._config)
            config_data["rows_data"] = self._rows_data
            config_data["resources"] = self._resources
            config_data["unique_id"] = self.flow_id

            resource = next((r for r in self._resources if r["id"] == self._config[CONF_RESOURCE_ID]), None)
            
            self.hass.data[DOMAIN][self.flow_id] = {
                "api": OpenDataBolzanoApiClient(self.hass),
                "config": config_data,
                "rows_data": self._rows_data,
                "resources": self._resources
            }
            return self.async_create_entry(
                title=resource.get("name", NAME),  # Usa il nome della risorsa
                data=config_data
            )
        if self._config.get("resource_format", "").upper() == "WMS":
            preview_text = "Tracker per il layer WMS verrà creato."
        else:
            sensor_previews = []
            for row in [self._rows_data[idx] for idx in self._config.get("selected_rows", [])]:
                row_name = row.get("name", "row")
                row_name_clean = re.sub(
                    r'[^a-z0-9_]+', '_', row_name.lower().strip())
                for field_type, key in self._config["selected_fields"]:
                    if field_type == "measurement":
                        measurement = next((m for m in row.get("measurements", [])
                                            if m.get("code", "").lower() == key.lower()), None)
                        if measurement and "description" in measurement:
                            sensor_field = f"{key} ({measurement.get('description', key)})".lower(
                            ).replace(" ", "_")
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
