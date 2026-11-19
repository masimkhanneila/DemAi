from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.station import StationCreate, StationResponse, StationUpdate
from services import station_service

router = APIRouter(prefix="/stations", tags=["Stations"])

_404 = {404: {"description": "Station not found"}}


@router.post("", response_model=StationResponse, status_code=status.HTTP_201_CREATED)
def create_station(data: StationCreate, db: Session = Depends(get_db)):
    return station_service.create_station(db, data)


@router.get("", response_model=list[StationResponse])
def list_stations(db: Session = Depends(get_db)):
    return station_service.list_stations(db)


@router.get("/{station_id}", response_model=StationResponse, responses=_404)
def get_station(station_id: int, db: Session = Depends(get_db)):
    return station_service.get_station(db, station_id)


@router.patch("/{station_id}", response_model=StationResponse, responses=_404)
def update_station(station_id: int, data: StationUpdate, db: Session = Depends(get_db)):
    return station_service.update_station(db, station_id, data)


@router.delete(
    "/{station_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_404, 409: {"description": "Station is used by a route"}},
)
def delete_station(station_id: int, db: Session = Depends(get_db)):
    station_service.delete_station(db, station_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
