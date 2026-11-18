from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.station import Station
from schemas.station import AirQuality, StationCreate, StationUpdate


def classify_air_quality(pm25: float) -> AirQuality:
    if pm25 < 15:
        return AirQuality.low
    if pm25 < 35:
        return AirQuality.moderate
    return AirQuality.high


def _to_response(station: Station) -> dict:
    return {
        "id": station.id,
        "name": station.name,
        "location": station.location,
        "pm25": station.pm25,
        "air_quality": classify_air_quality(station.pm25),
    }


def _get_or_404(db: Session, station_id: int) -> Station:
    station = db.get(Station, station_id)
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station with id {station_id} not found",
        )
    return station


def _commit(db: Session, conflict_detail: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict_detail)


def create_station(db: Session, data: StationCreate) -> dict:
    station = Station(**data.model_dump())
    db.add(station)
    _commit(db, "Station violates a database constraint")
    db.refresh(station)
    return _to_response(station)


def list_stations(db: Session) -> list[dict]:
    stations = db.scalars(select(Station).order_by(Station.id)).all()
    return [_to_response(s) for s in stations]


def get_station(db: Session, station_id: int) -> dict:
    return _to_response(_get_or_404(db, station_id))


def update_station(db: Session, station_id: int, data: StationUpdate) -> dict:
    station = _get_or_404(db, station_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one field to update: name, location, pm25",
        )
    for field, value in changes.items():
        setattr(station, field, value)
    _commit(db, "Station violates a database constraint")
    db.refresh(station)
    return _to_response(station)


def delete_station(db: Session, station_id: int) -> None:
    station = _get_or_404(db, station_id)
    conflict = f"Station {station_id} is used by a route and cannot be deleted"
    if station.routes:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict)
    db.delete(station)
    
    _commit(db, conflict)




def station_exists(db: Session, station_id: int) -> bool:
    return db.get(Station, station_id) is not None


def get_station_pm25(db: Session, station_id: int) -> float:
    return _get_or_404(db, station_id).pm25
