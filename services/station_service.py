"""Бизнес-логика станций мониторинга воздуха.

Станции хранятся в store.stations как обычные словари:
    stations[id] = {"id": int, "name": str, "location": str, "pm25": float}

Person 2 / Person 3 могут читать PM2.5 так: store.stations[station_id]["pm25"]
или через get_station_pm25(station_id).
"""

from fastapi import HTTPException, status

import store
from schemas.station import AirQuality, StationCreate, StationUpdate

_next_id = 1


def _generate_id() -> int:
    # Счётчик не уменьшается, поэтому ID удалённой станции не переиспользуется
    global _next_id
    new_id = max(_next_id, max(store.stations, default=0) + 1)
    _next_id = new_id + 1
    return new_id


def classify_air_quality(pm25: float) -> AirQuality:
    """Low: < 15, Moderate: 15 <= x < 35, High: >= 35 (см. README)."""
    if pm25 < 15:
        return AirQuality.low
    if pm25 < 35:
        return AirQuality.moderate
    return AirQuality.high


def _to_response(station: dict) -> dict:
    return {**station, "air_quality": classify_air_quality(station["pm25"])}


def _get_or_404(station_id: int) -> dict:
    station = store.stations.get(station_id)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station with id {station_id} not found",
        )
    return station


def _route_station_id(route):
    # Маршрут может храниться как dict или как Pydantic-модель — поддерживаем оба
    if isinstance(route, dict):
        return route.get("station_id")
    return getattr(route, "station_id", None)


def is_station_used_by_route(station_id: int) -> bool:
    return any(_route_station_id(route) == station_id for route in store.routes.values())


# ---------- функции, которые вызывает роутер ----------

def create_station(data: StationCreate) -> dict:
    station_id = _generate_id()
    station = {"id": station_id, **data.model_dump()}
    store.stations[station_id] = station
    return _to_response(station)


def list_stations() -> list[dict]:
    return [_to_response(s) for s in store.stations.values()]


def get_station(station_id: int) -> dict:
    return _to_response(_get_or_404(station_id))


def update_station(station_id: int, data: StationUpdate) -> dict:
    station = _get_or_404(station_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one field to update: name, location, pm25",
        )
    station.update(changes)
    return _to_response(station)


def delete_station(station_id: int) -> None:
    _get_or_404(station_id)
    if is_station_used_by_route(station_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Station {station_id} is used by a route and cannot be deleted",
        )
    del store.stations[station_id]


# ---------- хелперы для других частей API ----------

def station_exists(station_id: int) -> bool:
    return station_id in store.stations


def get_station_pm25(station_id: int) -> float:
    return _get_or_404(station_id)["pm25"]
