from fastapi import APIRouter, Response, status

from schemas.station import StationCreate, StationResponse, StationUpdate
from services import station_service

router = APIRouter(prefix="/stations", tags=["Stations"])

_404 = {404: {"description": "Station not found"}}


@router.post("", response_model=StationResponse, status_code=status.HTTP_201_CREATED)
def create_station(data: StationCreate):
    return station_service.create_station(data)


@router.get("", response_model=list[StationResponse])
def list_stations():
    return station_service.list_stations()


@router.get("/{station_id}", response_model=StationResponse, responses=_404)
def get_station(station_id: int):
    return station_service.get_station(station_id)


@router.patch("/{station_id}", response_model=StationResponse, responses=_404)
def update_station(station_id: int, data: StationUpdate):
    return station_service.update_station(station_id, data)


@router.delete(
    "/{station_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_404, 409: {"description": "Station is used by a route"}},
)
def delete_station(station_id: int):
    station_service.delete_station(station_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
