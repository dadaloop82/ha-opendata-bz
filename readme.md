# OpenData Alto Adige Integration for Home Assistant

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

### Via HACS
1. Open HACS in Home Assistant.
2. Go to **Integrations**.
3. Click the **+ Explore & Add Repositories** button.
4. Search for **"OpenData Alto Adige"**.
5. Click **Install** and follow the on-screen instructions.
6. Restart Home Assistant if required.

### Manual Installation
1. Copy the entire `custom_components/provbz_opendata` folder into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Go to **Configuration > Integrations**.
4. Click the **+ ADD INTEGRATION** button and search for **"OpenData Alto Adige"**.

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

## Data Sources
All data is retrieved from the Open Data Hub of the Autonomous Province of Bolzano. Data is available under various open licenses, including:
- CC0 1.0 Universal
- CC-BY 4.0
- Other open licenses as specified per dataset

For detailed licensing information, please check the specific dataset on [data.civis.bz.it](https://data.civis.bz.it/).

## Available Data Types
- Environmental monitoring stations  
- Weather stations  
- Traffic monitoring points  
- Water quality monitoring  
- And many more...

## Entity Types

### Sensors (JSON Data)
- Automatically created for numerical and status data.
- Automatic unit detection.
- Multilingual attribute support.
- Regular updates based on source data.

### Device Trackers (WFS/WMS Data)
- Automatically created for geographical features.
- Displayed on the Home Assistant map.
- Include all source attributes.
- Automatic coordinate mapping and real-time position updates.

## Limitations
- Update frequency depends on the data source.
- Some datasets may not be available in all languages.
- WFS features are currently limited to point geometries.
- WMS requests require proper parameter configuration.
- An active internet connection is required for updates.

## Contributing
Contributions are welcome! Please review our contributing guidelines before submitting pull requests.

## License
This integration is licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

> **Note:** Although this integration is open source, the data accessed is provided by the Autonomous Province of Bolzano under various open licenses. Please review each dataset's license before use.

## Support
For bugs and feature requests, please use the [GitHub issue tracker](https://github.com/dadaloop82/ha-opendata-bolzano/issues).

## Acknowledgments
- Data provided by the Autonomous Province of Bolzano.
- Thanks to all contributors.
- Built for the Home Assistant community.

## Changelog
See [CHANGELOG.md](CHANGELOG.md) for release notes and changes.