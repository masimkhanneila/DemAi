from fastapi import APIRouter, Response, status

from schemas.saved_route import SavedRouteCreate, SavedRouteResponse, SavedRouteUpdate
from services import saved_route_service


router = APIRouter(prefix="/saved-routes", tags=["Saved Routes"])


@router.post("", response_model=SavedRouteResponse, status_code=status.HTTP_201_CREATED)
def create_saved_route(payload: SavedRouteCreate):
    return saved_route_service.create_saved_route(payload)


@router.get("", response_model=list[SavedRouteResponse])
def list_saved_routes():
    return saved_route_service.list_saved_routes()


@router.get("/{saved_route_id}", response_model=SavedRouteResponse)
def get_saved_route(saved_route_id: int):
    return saved_route_service.get_saved_route(saved_route_id)


@router.patch("/{saved_route_id}", response_model=SavedRouteResponse)
def update_saved_route(saved_route_id: int, payload: SavedRouteUpdate):
    return saved_route_service.update_saved_route(saved_route_id, payload)


@router.delete("/{saved_route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_route(saved_route_id: int):
    saved_route_service.delete_saved_route(saved_route_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)