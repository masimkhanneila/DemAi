"""Client for the Open-Meteo Air Quality API.

Open-Meteo returns *modelled* PM2.5 estimates (CAMS forecasts) for a coordinate,
not readings from a physical sensor at the station.
Docs: https://open-meteo.com/en/docs/air-quality-api
"""

import math
from dataclasses import dataclass
from typing import Optional

import httpx

OPEN_METEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Fail fast: connecting may take up to 5 s, the whole request up to 10 s.
REQUEST_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class AirQualityError(Exception):
    """Base class for every failure of the external Air Quality API."""


class AirQualityTimeoutError(AirQualityError):
    """Open-Meteo did not answer in time."""


class AirQualityUnavailableError(AirQualityError):
    """Open-Meteo answered, but has no PM2.5 value for this location/time."""


class AirQualityUpstreamError(AirQualityError):
    """Network error, error status code, or a response in an unexpected format."""


@dataclass(frozen=True)
class AirQualityReading:
    pm25: float
    measured_at: Optional[str]  # time of the modelled value (GMT), e.g. "2026-11-26T13:00"


def fetch_current_pm25(
    latitude: float,
    longitude: float,
    client: Optional[httpx.Client] = None,
) -> AirQualityReading:
    """Request the current PM2.5 (µg/m³) for one coordinate.

    `client` lets tests pass an httpx.Client with a mock transport,
    so tests never call the real API.
    """
    params = {"latitude": latitude, "longitude": longitude, "current": "pm2_5"}

    try:
        if client is None:
            with httpx.Client(timeout=REQUEST_TIMEOUT) as own_client:
                response = own_client.get(OPEN_METEO_AIR_QUALITY_URL, params=params)
        else:
            response = client.get(OPEN_METEO_AIR_QUALITY_URL, params=params)
    except httpx.TimeoutException as exc:
        raise AirQualityTimeoutError("Open-Meteo did not respond in time") from exc
    except httpx.RequestError as exc:
        raise AirQualityUpstreamError(f"Could not reach Open-Meteo: {exc.__class__.__name__}") from exc

    if response.status_code != 200:
        raise AirQualityUpstreamError(
            f"Open-Meteo returned HTTP {response.status_code}: {_error_reason(response)}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise AirQualityUpstreamError("Open-Meteo returned a non-JSON response") from exc

    current = data.get("current") if isinstance(data, dict) else None
    if not isinstance(current, dict):
        raise AirQualityUpstreamError("Open-Meteo response has no 'current' block")

    value = current.get("pm2_5")
    if value is None:
        raise AirQualityUnavailableError("PM2.5 is not available for this location right now")

    # bool is a subclass of int in Python, so exclude it explicitly
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AirQualityUpstreamError("Open-Meteo returned a non-numeric PM2.5 value")
    pm25 = float(value)
    if not math.isfinite(pm25) or pm25 < 0:
        raise AirQualityUpstreamError("Open-Meteo returned an invalid PM2.5 value")

    return AirQualityReading(pm25=round(pm25, 2), measured_at=current.get("time"))


def _error_reason(response: httpx.Response) -> str:
    """Open-Meteo errors look like {"error": true, "reason": "..."}."""
    try:
        body = response.json()
    except ValueError:
        return "no details"
    if isinstance(body, dict) and body.get("reason"):
        return str(body["reason"])[:200]
    return "no details"