from typing import Any

import httpx
from mcp.server import MCPServer

# Initialize MCPServer
mcp = MCPServer("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"


async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Call the NWS API and return the JSON response, or None if it fails."""
    headers = {
        "User-Agent": USER_AGENT,  # NWS requires a User-Agent
        "Accept": "application/geo+json",
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


def format_alert(feature: dict) -> str:
    """Turn one weather alert into readable text."""
    props = feature["properties"]
    return (
        f"Event: {props.get('event', 'Unknown')}\n"
        f"Area: {props.get('areaDesc', 'Unknown')}\n"
        f"Severity: {props.get('severity', 'Unknown')}\n"
        f"Description: {props.get('description', 'No description available')}\n"
        f"Instructions: {props.get('instruction', 'No specific instructions provided')}"
    )

@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get active weather alerts for a US state.

    Args:
        state: Two-letter US state code, e.g. CA or NY
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state.upper()}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts."
    if not data["features"]:
        return "No active alerts for this state."

    return "\n---\n".join(format_alert(f) for f in data["features"])


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get the weather forecast for a US location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    points = await make_nws_request(f"{NWS_API_BASE}/points/{latitude},{longitude}")
    if not points:
        return "Unable to fetch forecast data for this location."

    forecast = await make_nws_request(points["properties"]["forecast"])
    if not forecast:
        return "Unable to fetch the detailed forecast."

    results = []
    for p in forecast["properties"]["periods"][:5]:
        results.append(
            f"{p['name']}:\n"
            f"Temperature: {p['temperature']}°{p['temperatureUnit']}\n"
            f"Wind: {p['windSpeed']} {p['windDirection']}\n"
            f"Forecast: {p['detailedForecast']}"
        )
    return "\n---\n".join(results)




OPEN_METEO_GEO = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Freezing fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Rain showers", 81: "Rain showers", 82: "Heavy rain showers",
    85: "Snow showers", 86: "Heavy snow showers", 95: "Thunderstorm",
}

@mcp.tool()
async def get_world_forecast(city: str, country_code: str = "", days: int = 7) -> str:
    """Get a daily weather forecast for any city worldwide, e.g. Zurich or Vienna.

    Args:
        city: City name, e.g. Zurich, Lucerne, Vienna, Salzburg
        country_code: Optional 2-letter country code to avoid mix-ups, e.g. CH or AT
        days: Number of days to forecast, 1 to 16
    """
    geo_params = {"name": city, "count": 1, "language": "en", "format": "json"}
    if country_code:
        geo_params["countryCode"] = country_code.upper()
    geo = await fetch_json(OPEN_METEO_GEO, geo_params)
    if not geo or not geo.get("results"):
        return f"Couldn't find a location called {city}."
    place = geo["results"][0]

    params = {
        "latitude": place["latitude"],
        "longitude": place["longitude"],
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_sum,precipitation_probability_max,wind_speed_10m_max",
        "timezone": "auto",
        "forecast_days": max(1, min(days, 16)),
    }
    data = await fetch_json(OPEN_METEO_FORECAST, params)
    if not data or "daily" not in data:
        return "Unable to fetch the forecast."

    d = data["daily"]
    lines = [f"Forecast for {place['name']}, {place.get('country', '')}:"]
    for i, date in enumerate(d["time"]):
        chance = d["precipitation_probability_max"][i]
        chance_text = f"{chance}% chance" if chance is not None else "chance n/a"
        lines.append(
            f"{date}: {WEATHER_CODES.get(d['weather_code'][i], 'Unknown')}, "
            f"{d['temperature_2m_min'][i]} to {d['temperature_2m_max'][i]}°C, "
            f"rain {d['precipitation_sum'][i]} mm ({chance_text}), "
            f"wind up to {d['wind_speed_10m_max'][i]} km/h"
        )
    return "\n".join(lines)
async def fetch_json(url: str, params: dict) -> dict | None:
    """GET a URL with query parameters and return JSON, or None on failure."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


def main():
    # Start the server and wait for Claude to talk to it
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
