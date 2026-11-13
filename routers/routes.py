from fastapi import APIRouter, Query, Response, status

from schemas.route import RouteComparison, RouteCreate, RouteResponse, RouteUpdate, RouteWithExposure
from services import route_service

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.get("", response_model=list[RouteResponse])
def list_routes():
    return route_service.list_routes()


@router.post("", response_model=RouteResponse, status_code=status.HTTP_201_CREATED)
def create_route(payload: RouteCreate):
    return route_service.create_route(payload)


@router.get("/compare", response_model=RouteComparison)
def compare_routes(start: str = Query(min_length=1), end: str = Query(min_length=1)):
    return route_service.compare_routes(start, end)


@router.get("/{route_id}", response_model=RouteResponse)
def get_route(route_id: int):
    return route_service.get_route(route_id)


@router.get("/{route_id}/exposure", response_model=RouteWithExposure)
def get_route_exposure(route_id: int):
    return route_service.get_route_exposure(route_id)


@router.patch("/{route_id}", response_model=RouteResponse)
def update_route(route_id: int, payload: RouteUpdate):
    return route_service.update_route(route_id, payload)


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(route_id: int):
    route_service.delete_route(route_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
