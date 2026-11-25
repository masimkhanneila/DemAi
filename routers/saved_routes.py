from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies.auth import get_current_user
from models.user import User
from schemas.saved_route import (
    SavedRouteCreate,
    SavedRouteResponse,
    SavedRouteUpdate,
)
from services import saved_route_service


router = APIRouter(
    prefix="/saved-routes",
    tags=["Saved Routes"],
)


@router.post(
    "",
    response_model=SavedRouteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_saved_route(
    payload: SavedRouteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return saved_route_service.create_saved_route(
        payload,
        owner_id=current_user.id,
        db=db,
    )


@router.get("", response_model=list[SavedRouteResponse])
def list_saved_routes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return saved_route_service.list_saved_routes(
        owner_id=current_user.id,
        db=db,
    )


@router.get("/{saved_route_id}", response_model=SavedRouteResponse)
def get_saved_route(
    saved_route_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return saved_route_service.get_saved_route(
        saved_route_id,
        owner_id=current_user.id,
        db=db,
    )


@router.patch("/{saved_route_id}", response_model=SavedRouteResponse)
def update_saved_route(
    saved_route_id: int,
    payload: SavedRouteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return saved_route_service.update_saved_route(
        saved_route_id,
        payload,
        owner_id=current_user.id,
        db=db,
    )


@router.delete(
    "/{saved_route_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_saved_route(
    saved_route_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    saved_route_service.delete_saved_route(
        saved_route_id,
        owner_id=current_user.id,
        db=db,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)