"""Assignment 7 — Open-Meteo Air Quality integration (Member 1).

These tests never call the real Open-Meteo API:
- service tests use an httpx.MockTransport that fakes HTTP responses;
- endpoint tests replace fetch_current_pm25 with monkeypatch.
"""

import httpx
import pytest

from models.station import Station
from services import air_quality_service
from services.air_quality_service import (
    AirQualityReading,
    AirQualityTimeoutError,
    AirQualityUnavailableError,
    AirQualityUpstreamError,
    fetch_current_pm25,
)


# ---------- helpers ----------

def mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def json_response(body, status_code=200):
    return lambda request: httpx.Response(status_code, json=body)


OK_BODY = {
    "latitude": 43.2,
    "longitude": 76.9,
    "current_units": {"time": "iso8601", "interval": "seconds", "pm2_5": "μg/m³"},
    "current": {"time": "2026-11-26T13:00", "interval": 3600, "pm2_5": 23.456},
}


# ---------- air_quality_service: talking to Open-Meteo ----------

def test_fetch_sends_coordinates_and_parses_pm25():
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=OK_BODY)

    reading = fetch_current_pm25(43.2389, 76.8897, client=mock_client(handler))

    assert reading == AirQualityReading(pm25=23.46, measured_at="2026-11-26T13:00")
    assert seen["params"] == {"latitude": "43.2389", "longitude": "76.8897", "current": "pm2_5"}


def test_fetch_timeout():
    def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(AirQualityTimeoutError):
        fetch_current_pm25(43.2, 76.9, client=mock_client(handler))


def test_fetch_network_error():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(AirQualityUpstreamError):
        fetch_current_pm25(43.2, 76.9, client=mock_client(handler))


def test_fetch_error_status_includes_reason():
    body = {"error": True, "reason": "Latitude must be in range of -90 to 90°."}
    with pytest.raises(AirQualityUpstreamError, match="HTTP 400.*Latitude must be in range"):
        fetch_current_pm25(43.2, 76.9, client=mock_client(json_response(body, 400)))


def test_fetch_missing_value_is_unavailable():
    body = {**OK_BODY, "current": {"time": "2026-11-26T13:00", "pm2_5": None}}
    with pytest.raises(AirQualityUnavailableError):
        fetch_current_pm25(43.2, 76.9, client=mock_client(json_response(body)))


@pytest.mark.parametrize("body", [
    {"latitude": 43.2},                                  # no "current" block
    {"current": {"pm2_5": "high"}},                      # not a number
    {"current": {"pm2_5": -3}},                          # negative
    {"current": {"pm2_5": True}},                        # bool is not a measurement
])
def test_fetch_rejects_unexpected_payloads(body):
    with pytest.raises(AirQualityUpstreamError):
        fetch_current_pm25(43.2, 76.9, client=mock_client(json_response(body)))


def test_fetch_rejects_non_json():
    handler = lambda request: httpx.Response(200, text="<html>maintenance</html>")
    with pytest.raises(AirQualityUpstreamError):
        fetch_current_pm25(43.2, 76.9, client=mock_client(handler))


# ---------- endpoint: POST /stations/{id}/refresh-air-quality ----------

@pytest.fixture
def located_station(db_session):
    station = Station(name="Almaty center", location="Almaty", pm25=80,
                      latitude=43.2389, longitude=76.8897)
    db_session.add(station)
    db_session.flush()
    return station


def fake_fetch(value=None, error=None):
    def _fetch(latitude, longitude):
        if error is not None:
            raise error
        return AirQualityReading(pm25=value, measured_at="2026-11-26T13:00")
    return _fetch


def refresh(client, station_id):
    return client.post(f"/stations/{station_id}/refresh-air-quality")


def test_refresh_saves_pm25_and_updates_exposure(client, db_session, located_station, monkeypatch):
    monkeypatch.setattr(air_quality_service, "fetch_current_pm25", fake_fetch(12.5))
    route = client.post("/routes", json={
        "start": "Medeu", "end": "Center", "distance_km": 2.3,
        "duration_min": 10, "station_id": located_station.id,
    }).json()
    assert client.get(f"/routes/{route['id']}/exposure").json()["exposure_score"] == 800

    response = refresh(client, located_station.id)

    assert response.status_code == 200
    body = response.json()
    assert body["pm25"] == 12.5
    assert body["air_quality"] == "low"
    assert (body["latitude"], body["longitude"]) == (43.2389, 76.8897)
    db_session.expire_all()
    assert db_session.get(Station, located_station.id).pm25 == 12.5
    # Routes read the stored pm25, so exposure follows the refreshed value
    assert client.get(f"/routes/{route['id']}/exposure").json()["exposure_score"] == 125


@pytest.mark.parametrize("error, status_code", [
    (AirQualityTimeoutError("Open-Meteo did not respond in time"), 504),
    (AirQualityUnavailableError("PM2.5 is not available"), 503),
    (AirQualityUpstreamError("Open-Meteo returned HTTP 500"), 502),
])
def test_refresh_failure_keeps_old_pm25(client, db_session, located_station, monkeypatch,
                                        error, status_code):
    monkeypatch.setattr(air_quality_service, "fetch_current_pm25", fake_fetch(error=error))

    response = refresh(client, located_station.id)

    assert response.status_code == status_code
    db_session.expire_all()
    assert db_session.get(Station, located_station.id).pm25 == 80


def test_refresh_station_without_coordinates(client, station_ids, monkeypatch):
    def must_not_be_called(latitude, longitude):
        raise AssertionError("API must not be called without coordinates")
    monkeypatch.setattr(air_quality_service, "fetch_current_pm25", must_not_be_called)

    response = refresh(client, station_ids[0])

    assert response.status_code == 409
    assert "no coordinates" in response.json()["detail"]


def test_refresh_missing_station(client):
    assert refresh(client, 999_999).status_code == 404


def test_refresh_requires_admin(api_client, auth_headers, located_station, monkeypatch):
    monkeypatch.setattr(air_quality_service, "fetch_current_pm25", fake_fetch(12.5))
    url = f"/stations/{located_station.id}/refresh-air-quality"

    assert api_client.post(url).status_code == 401
    assert api_client.post(url, headers=auth_headers["user"]).status_code == 403
    assert api_client.post(url, headers=auth_headers["admin"]).status_code == 200


# ---------- Stations CRUD with coordinates ----------

def test_create_station_with_and_without_coordinates(client):
    with_coords = client.post("/stations", json={
        "name": "Medeu", "location": "Almaty", "pm25": 30,
        "latitude": 43.1575, "longitude": 77.0589,
    })
    without_coords = client.post("/stations", json={
        "name": "Old style", "location": "Almaty", "pm25": 30,
    })

    assert with_coords.status_code == 201
    assert (with_coords.json()["latitude"], with_coords.json()["longitude"]) == (43.1575, 77.0589)
    assert without_coords.status_code == 201
    assert without_coords.json()["latitude"] is None


@pytest.mark.parametrize("coords", [
    {"latitude": 43.2},                      # only one of the pair
    {"latitude": 91, "longitude": 76.9},     # out of range
    {"latitude": 43.2, "longitude": 181},
])
def test_create_station_rejects_bad_coordinates(client, coords):
    payload = {"name": "X", "location": "Almaty", "pm25": 10, **coords}
    assert client.post("/stations", json=payload).status_code == 422


def test_update_station_coordinates(client, station_ids):
    ok = client.patch(f"/stations/{station_ids[0]}", json={"latitude": 43.2, "longitude": 76.9})
    only_one = client.patch(f"/stations/{station_ids[0]}", json={"latitude": 43.3})
    null = client.patch(f"/stations/{station_ids[0]}", json={"latitude": None, "longitude": None})

    assert ok.status_code == 200
    assert (ok.json()["latitude"], ok.json()["longitude"]) == (43.2, 76.9)
    assert only_one.status_code == 422
    assert null.status_code == 422