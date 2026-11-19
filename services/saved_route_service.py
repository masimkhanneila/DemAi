from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from models.route import Route
from models.saved_route import SavedRoute
from schemas.saved_route import SavedRouteCreate, SavedRouteUpdate


def _get_saved_route(saved_route_id: int, db: Session) -> SavedRoute:
    saved_route = db.get(
        SavedRoute,
        saved_route_id,
        options=(joinedload(SavedRoute.route).joinedload(Route.station),),
    )
    if saved_route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Saved route not found"
        )
    return saved_route


def _get_route(route_id: int, db: Session) -> Route:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Route not found"
        )

    if route.station is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Referenced monitoring station is missing",
        )

    return route


def _with_exposure(saved_route: SavedRoute) -> dict:
    route = saved_route.route
    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Route not found"
        )
    station = route.station
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Referenced monitoring station is missing",
        )
    return {
        "id": saved_route.id,
        "user_id": saved_route.user_id,
        "route_id": saved_route.route_id,
        "label": saved_route.label,
        "preference": saved_route.preference,
        "exposure_score": round(float(station.pm25) * route.duration_min, 2),
    }


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        detail = "Database constraint or relationship conflict"
        if getattr(exc.orig, "sqlstate", None) == "23505":
            detail = "This route is already saved by the user"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=detail
        ) from exc


def _save(saved_route: SavedRoute, db: Session) -> dict:
    db.add(saved_route)
    _commit(db)
    db.refresh(saved_route)
    return _with_exposure(saved_route)


def create_saved_route(payload: SavedRouteCreate, db: Session) -> dict:
    route = _get_route(payload.route_id, db)
    saved_route = SavedRoute(**payload.model_dump(), route=route)
    return _save(saved_route, db)


def list_saved_routes(db: Session) -> list[dict]:
    saved_routes = db.scalars(
        select(SavedRoute)
        .options(joinedload(SavedRoute.route).joinedload(Route.station))
        .order_by(SavedRoute.id)
    ).all()
    return [_with_exposure(saved_route) for saved_route in saved_routes]


def get_saved_route(saved_route_id: int, db: Session) -> dict:
    return _with_exposure(_get_saved_route(saved_route_id, db))


def update_saved_route(
    saved_route_id: int, payload: SavedRouteUpdate, db: Session
) -> dict:
    saved_route = _get_saved_route(saved_route_id, db)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Provide a field to update",
        )
    route = _get_route(changes.get("route_id", saved_route.route_id), db)
    for field, value in changes.items():
        setattr(saved_route, field, value)
    saved_route.route = route
    return _save(saved_route, db)


def delete_saved_route(saved_route_id: int, db: Session) -> None:
    saved_route = _get_saved_route(saved_route_id, db)
    db.delete(saved_route)
    _commit(db)
