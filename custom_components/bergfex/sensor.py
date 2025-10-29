import logging
from datetime import timedelta
from typing import Any, cast

from bs4 import BeautifulSoup
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BASE_URL,
    CONF_COUNTRY,
    CONF_SKI_AREA,
    COORDINATORS,
    COUNTRIES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Bergfex sensor entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(COORDINATORS, {})

    # Handle old config entries that don't have the 'country' key by defaulting to Austria
    country_name = entry.data.get(CONF_COUNTRY, "Österreich")
    country_path = COUNTRIES[country_name]
    area_name = entry.data["name"]

    if country_name not in hass.data[DOMAIN][COORDINATORS]:
        _LOGGER.debug("Creating new coordinator for country: %s", country_name)
        session = async_get_clientsession(hass)

        async def async_update_data():
            """Fetch and parse data for all ski areas in a country."""
            try:
                url = f"{BASE_URL}{country_path}"
                async with session.get(url, allow_redirects=True) as response:
                    response.raise_for_status()
                    html = await response.text()
                return parse_overview_data(html)
            except Exception as err:
                raise UpdateFailed(f"Error communicating with Bergfex: {err}")

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"bergfex_{country_name}",
            update_method=async_update_data,
            update_interval=SCAN_INTERVAL,
        )
        hass.data[DOMAIN][COORDINATORS][country_name] = coordinator

    coordinator = hass.data[DOMAIN][COORDINATORS][country_name]
    await coordinator.async_config_entry_first_refresh()

    sensors = [
        BergfexSensor(coordinator, entry, "Status", "status", icon="mdi:ski"),
        BergfexSensor(
            coordinator,
            entry,
            "Snow Valley",
            "snow_valley",
            icon="mdi:snowflake",
            unit="cm",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Snow Mountain",
            "snow_mountain",
            icon="mdi:snowflake",
            unit="cm",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        BergfexSensor(
            coordinator,
            entry,
            "New Snow",
            "new_snow",
            icon="mdi:weather-snowy-heavy",
            unit="cm",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Lifts Open",
            "lifts_open_count",
            icon="mdi:gondola",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Lifts Total",
            "lifts_total_count",
            icon="mdi:map-marker-distance",
        ),
        BergfexSensor(
            coordinator, entry, "Last Update", "last_update", icon="mdi:clock-outline"
        ),
    ]
    async_add_entities(sensors)


def parse_overview_data(html: str) -> dict[str, dict[str, Any]]:
    """Parse the HTML of the overview page and return a dict of all ski areas."""
    soup = BeautifulSoup(html, "html.parser")
    results = {}

    table = soup.find("table", class_="snow")
    if not table:
        _LOGGER.warning("Could not find overview data table with class 'snow'")
        return {}

    for row in table.find_all("tr")[1:]:  # Skip header row
        cols = row.find_all("td")
        if len(cols) < 6:
            continue

        link = cols[0].find("a")
        if not (link and link.get("href")):
            continue

        area_path = link["href"]
        area_data = {}

        # Snow Depths (Valley, Mountain) and New Snow from data-value
        area_data["snow_valley"] = cols[1].get("data-value")
        area_data["snow_mountain"] = cols[2].get("data-value")
        area_data["new_snow"] = cols[3].get("data-value")

        # Lifts and Status (from column 4)
        lifts_cell = cols[4]
        status_div = lifts_cell.find("div", class_="icon-status")
        if status_div:
            classes = status_div.get("class", [])
            if "icon-status1" in classes:
                area_data["status"] = "Open"
            elif "icon-status0" in classes:
                area_data["status"] = "Closed"
            else:
                area_data["status"] = "Unknown"

        lifts_raw = lifts_cell.text.strip()
        lifts_open = None
        lifts_total = None

        if "/" in lifts_raw:
            parts = lifts_raw.split("/")
            if len(parts) == 2:
                try:
                    lifts_open = int(parts[0].strip())
                except ValueError:
                    _LOGGER.debug("Could not parse lifts_open_count: %s", parts[0].strip())
                try:
                    lifts_total = int(parts[1].strip())
                except ValueError:
                    _LOGGER.debug("Could not parse lifts_total_count: %s", parts[1].strip())
        elif lifts_raw.isdigit():
            try:
                lifts_open = int(lifts_raw)
            except ValueError:
                _LOGGER.debug("Could not parse lifts_open_count: %s", lifts_raw)

        if lifts_open is not None:
            area_data["lifts_open_count"] = lifts_open
        if lifts_total is not None:
            area_data["lifts_total_count"] = lifts_total

        # Last Update - Get timestamp from data-value on the <td> if available
        if "data-value" in cols[5].attrs:
            area_data["last_update"] = cols[5]["data-value"]
        else:
            area_data["last_update"] = cols[5].text.strip()  # Fallback to text

        # Clean up "-" values
        results[area_path] = {k: v for k, v in area_data.items() if v not in ("-", "")}

    return results


class BergfexSensor(SensorEntity):
    """Representation of a Bergfex Sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_name: str,
        data_key: str,
        icon: str | None = None,
        unit: str | None = None,
        state_class: SensorStateClass | None = None,
    ):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._area_name = entry.data["name"]
        self._area_path = entry.data[CONF_SKI_AREA]
        self._config_url = f"{BASE_URL}{self._area_path}"
        self._sensor_name = sensor_name
        self._data_key = data_key
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_unique_id = f"bergfex_{self._area_name.lower().replace(' ', '_')}_{self._sensor_name.lower().replace(' ', '_')}"
        self._attr_name = f"{self._area_name} {sensor_name}"

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        # Data for this specific ski area
        all_areas_data = cast(dict, self.coordinator.data)
        area_data = all_areas_data.get(self._area_path)

        if area_data and self._data_key in area_data:
            value = area_data[self._data_key]
            # Try to convert to integer if it's a number
            if isinstance(value, str) and value.isdigit():
                return int(value)
            return value

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self._data_key == "status":
            return {"link": self._config_url}
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._area_name)},
            "name": self._area_name,
            "manufacturer": "Bergfex",
            "model": "Ski Resort",
            "configuration_url": self._config_url,
        }

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
