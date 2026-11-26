"""Endpoint that refreshes a station's PM2.5 from the Open-Meteo Air Quality API.

Kept in its own router so the Assignment 7 integration does not edit
routers/stations.py (owned by the Stations CRUD / authorization work).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies.permissions import require_admin
from schemas.station import StationResponse
from services import station_service

router = APIRouter(prefix="/stations", tags=["Stations"])


@router.post(
    "/{station_id}/refresh-air-quality",
    response_model=StationResponse,
    summary="Refresh PM2.5 from Open-Meteo",
    description=(
        "Requests the current modelled PM2.5 estimate for the station's coordinates "
        "from the Open-Meteo Air Quality API and stores it as the station's pm25. "
        "On any external API failure the stored value is not changed."
    ),
    responses={
        404: {"description": "Station not found"},
        409: {"description": "Station has no coordinates"},
        502: {"description": "Open-Meteo returned an error or an invalid response"},
        503: {"description": "PM2.5 is not available for this location right now"},
        504: {"description": "Open-Meteo did not respond in time"},
    },
    dependencies=[Depends(require_admin)],
)
def refresh_air_quality(station_id: int, db: Session = Depends(get_db)):
    return station_service.refresh_air_quality(db, station_id)