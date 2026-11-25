from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies.permissions import require_admin
from schemas.route import (
    RouteComparison,
    RouteCreate,
    RouteResponse,
    RouteUpdate,
    RouteWithExposure,
)
from services import route_service

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.get("", response_model=list[RouteResponse])
def list_routes(db: Session = Depends(get_db)):
    return route_service.list_routes(db)


@router.post(
    "",
    response_model=RouteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_route(
    payload: RouteCreate,
    db: Session = Depends(get_db),
):
    return route_service.create_route(payload, db)


@router.get("/compare", response_model=RouteComparison)
def compare_routes(
    start: str = Query(min_length=1),
    end: str = Query(min_length=1),
    db: Session = Depends(get_db),
):
    return route_service.compare_routes(start, end, db)


@router.get("/{route_id}", response_model=RouteResponse)
def get_route(
    route_id: int,
    db: Session = Depends(get_db),
):
    return route_service.get_route(route_id, db)


@router.get(
    "/{route_id}/exposure",
    response_model=RouteWithExposure,
)
def get_route_exposure(
    route_id: int,
    db: Session = Depends(get_db),
):
    return route_service.get_route_exposure(route_id, db)


@router.patch(
    "/{route_id}",
    response_model=RouteResponse,
    dependencies=[Depends(require_admin)],
)
def update_route(
    route_id: int,
    payload: RouteUpdate,
    db: Session = Depends(get_db),
):
    return route_service.update_route(route_id, payload, db)


@router.delete(
    "/{route_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_route(
    route_id: int,
    db: Session = Depends(get_db),
):
    route_service.delete_route(route_id, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)