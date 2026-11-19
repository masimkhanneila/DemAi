from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.saved_route import SavedRouteCreate, SavedRouteResponse, SavedRouteUpdate
from services import saved_route_service


router = APIRouter(prefix="/saved-routes", tags=["Saved Routes"])


@router.post("", response_model=SavedRouteResponse, status_code=status.HTTP_201_CREATED)
def create_saved_route(payload: SavedRouteCreate, db: Session = Depends(get_db)):
    return saved_route_service.create_saved_route(payload, db)


@router.get("", response_model=list[SavedRouteResponse])
def list_saved_routes(db: Session = Depends(get_db)):
    return saved_route_service.list_saved_routes(db)


@router.get("/{saved_route_id}", response_model=SavedRouteResponse)
def get_saved_route(saved_route_id: int, db: Session = Depends(get_db)):
    return saved_route_service.get_saved_route(saved_route_id, db)


@router.patch("/{saved_route_id}", response_model=SavedRouteResponse)
def update_saved_route(
    saved_route_id: int, payload: SavedRouteUpdate, db: Session = Depends(get_db)
):
    return saved_route_service.update_saved_route(saved_route_id, payload, db)


@router.delete("/{saved_route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_route(saved_route_id: int, db: Session = Depends(get_db)):
    saved_route_service.delete_saved_route(saved_route_id, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
