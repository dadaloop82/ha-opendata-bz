# OpenData Alto Adige Integration for Home Assistant

<p align="center">
  <img src="https://github.com/dadaloop82/ha-opendata-bz/blob/main/custom_components/provbz_opendata/images/logo.png" alt="Logo OpenData Alto Adige" width="200">
</p>

## Overview

The **OpenData Alto Adige Integration** connects Home Assistant to the OpenData Hub of the Autonomous Province of Bolzano/Bozen, allowing you to integrate a variety of public data sources into your home automation system. The integration retrieves data directly from the Open Data Hub ([data.civis.bz.it](https://data.civis.bz.it/)) and updates in real time.

## Features

- **Multiple Data Categories:** Access data for Environment, Traffic, Weather, Water Quality, and more.
- **Data Source Support:** Works with both JSON and WFS (Web Feature Service) sources.
- **Automatic Entity Creation:** Dynamically creates entities based on your data selections.
- **Real-time Updates:** Continuously updates sensor values and device trackers.
- **Multilingual Support:** Interfaces and data attributes in Italian, German, and English.
- **Geographical Data Integration:** Automatic coordinate mapping and display of device trackers on the Home Assistant map.
- **WMS Support:** In addition to JSON data, support for WMS layers is provided to create device trackers.

## Installation

### Via HACS (Recommended)

1. Open HACS in Home Assistant.
2. Go to **Settings > Devices & Services**.
3. Click the **+ Add Integration** button.
4. Search for **"HACS"** and configure it if you haven't already.
5. Go to **HACS > Integrations**.
6. Click the **+ Explore & Add Repositories** button.
7. Add the following repository URL: `https://github.com/dadaloop82/ha-opendata-bz`
8. Select the **"OpenData Alto Adige"** integration and click **Install**.
9. Restart Home Assistant.
10. Go to **Settings > Devices & Services**, click **+ Add Integration**, and search for **"OpenData Alto Adige"** to configure the integration.

## Configuration

The integration provides a step-by-step configuration flow:

1. **Language Selection:** Choose your language (IT/DE/EN).
2. **Data Category Selection:** Select the thematic group you want to monitor.
3. **Dataset Selection:** Pick the dataset within the chosen group.
4. **Resource Type Selection:** Choose the data source type:
    - **For JSON resources:**
        - Select the data point(s) and fields you want to monitor. Sensors will be automatically created based on your selections.
    - **For WFS (and WMS) resources:**
        - Device trackers are automatically created to display geographical features on the Home Assistant map.

## Available Data Sources

This integration provides access to a wide range of open datasets, including:

### Weather Services

- **Radar meteorologico:** Real-time precipitation intensity.
- **Tendenza della temperatura:** 10-day temperature trends.
- **Diagramma del Föhn:** Foehn wind forecast.
- **Bollettino meteo:** Weather forecasts and current conditions.
- **Stazioni meteo e idrografiche:** Real-time meteorological station data.

### Health Services

- **Farmacie di turno:** List of open pharmacies.
- **Medici di turno:** On-call doctors.
- **Tempi di prenotazione:** Average wait times for medical appointments.
- **Qualità dell'aria:** Air quality and radiation measurements.

### Environmental & Geographical Data

- **Consumo di suolo ISPRA:** Land consumption maps.
- **Balneabilità dei laghi:** Lake swimming suitability.
- **Zone di rischio idrogeologico:** Flood risk areas.
- **Rete di monitoraggio corsi d'acqua:** Water monitoring stations.
- **Cave e torbiere:** Areas of quarries and peat bogs.
- **Piani paesaggistici:** Landscape plans and protected elements.
- **Teleriscaldamento:** District heating zones.

### Traffic & Infrastructure

- **Bollettino del traffico:** Real-time traffic alerts.
- **Zone servite da teleriscaldamento:** District heating zones.
- **Ostacoli alla viabilità:** Traffic obstacles like gates and barriers.

... and many more!

## Example Uses

- **Weather Tracking:** Display real-time weather conditions and forecasts.
- **Traffic Monitoring:** Get live traffic alerts for your area.
- **Environmental Monitoring:** Check water quality and pollution levels.
- **Public Services:** Find open pharmacies and on-call doctors.
- **Geographical Information:** Visualize protected areas, flood risk zones, and more on the map.

## More Information

- **Official OpenData Hub:** [data.civis.bz.it](https://data.civis.bz.it/)
- **Home Assistant Community Forum:** [community.home-assistant.io](https://community.home-assistant.io/)
- **Project Repository:** [GitHub](https://github.com/dadaloop82/ha-opendata-bolzano)

## Contribute

Contributions are welcome! Feel free to open issues or submit pull requests in the [GitHub repository](https://github.com/dadaloop82/ha-opendata-bolzano).

## License

This integration is licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

> **Note:** Although this integration is open source, the data accessed is provided by the Autonomous Province of Bolzano under various open licenses. Please review each dataset's license before use.