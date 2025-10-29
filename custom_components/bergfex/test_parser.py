# /config/custom_components/bergfex/test_parser.py

import asyncio
from typing import Any

import aiohttp
from bs4 import BeautifulSoup


def parse_overview_data(html: str) -> dict[str, dict[str, Any]]:
    """Parse the HTML of the overview page and return a dict of all ski areas."""
    soup = BeautifulSoup(html, "html.parser")
    results = {}

    table = soup.find("table", class_="snow")
    if not table:
        print("WARNING: Could not find overview data table with class 'snow'")
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
                    print(
                        f"WARNING: Could not parse lifts_open_count: {parts[0].strip()}"
                    )
                try:
                    lifts_total = int(parts[1].strip())
                except ValueError:
                    print(
                        f"WARNING: Could not parse lifts_total_count: {parts[1].strip()}"
                    )
        elif lifts_raw.isdigit():
            try:
                lifts_open = int(lifts_raw)
            except ValueError:
                print(f"WARNING: Could not parse lifts_open_count: {lifts_raw}")

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


async def main():
    """Hauptfunktion zum Testen des Parsers."""
    # Use the country overview URL to test the new logic
    test_url = "https://www.bergfex.at/oesterreich/schneewerte/"

    print(f"Testing data retrieval from: {test_url}")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(test_url, allow_redirects=True) as response:
                response.raise_for_status()
                html = await response.text()

                print("Page downloaded successfully. Starting parsing...")

                parsed_data = parse_overview_data(html)

                print("\n--- PARSING RESULT (first 5 entries) ---")
                if parsed_data:
                    # Print data for the first 5 ski areas as an example
                    for i, (path, data) in enumerate(parsed_data.items()):
                        if i >= 10:
                            break
                        print(f"Path: {path}, Data: {data}")
                else:
                    print("No data extracted.")
                print("---------------------------\n")

        except aiohttp.ClientError as e:
            print(f"Connection error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    # Führt die asynchrone main-Funktion aus
    asyncio.run(main())
