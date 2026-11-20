
from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.route import Route
from models.station import Station
from models.saved_route import SavedRoute
from schemas.route import RouteCreate, RouteUpdate


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Database constraint or relationship conflict",
        ) from exc


def _check_station(station_id: int, db: Session) -> None:
    if db.get(Station, station_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Monitoring station not found",
        )


def _get_existing_route(route_id: int, db: Session) -> Route:
    route = db.get(Route, route_id)

    if route is None:
        raise HTTPException(
            status_code=404,
            detail="Route not found",
        )

    return route


def _to_dict(route: Route) -> dict:
    return {
        "id": route.id,
        "start": route.start,
        "end": route.end,
        "distance_km": route.distance_km,
        "duration_min": route.duration_min,
        "station_id": route.station_id,
    }


def list_routes(db: Session) -> list[dict]:
    routes = db.scalars(select(Route).order_by(Route.id)).all()
    return [_to_dict(route) for route in routes]


def get_route(route_id: int, db: Session) -> dict:
    route = _get_existing_route(route_id, db)
    return _to_dict(route)


def create_route(payload: RouteCreate, db: Session) -> dict:
    _check_station(payload.station_id, db)

    route = Route(**payload.model_dump())

    db.add(route)
    _commit(db)
    db.refresh(route)

    return _to_dict(route)


def update_route(route_id: int,payload: RouteUpdate,db: Session,) -> dict:
    route = _get_existing_route(route_id, db)

    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=422,
            detail="Provide a field to update",
        )

    current = {
        field: getattr(route, field)
        for field in RouteCreate.model_fields
    }

    updated = {**current, **changes}

    try:
        validated = RouteCreate.model_validate(updated)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(
                include_context=False,
                include_url=False,
            ),
        ) from exc

    _check_station(validated.station_id, db)

    for field, value in validated.model_dump().items():
        setattr(route, field, value)

    _commit(db)
    db.refresh(route)

    return _to_dict(route)


def delete_route(route_id: int, db: Session) -> None:
    route = _get_existing_route(route_id, db)

    saved_id = db.scalar(
        select(SavedRoute.id)
        .where(SavedRoute.route_id == route_id)
        .limit(1)
    )

    if saved_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a route that is saved by a user",
        )

    db.delete(route)
    _commit(db)


def _with_exposure(route: Route, db: Session) -> dict:
    station = db.get(Station, route.station_id)

    if station is None:
        raise HTTPException(
            status_code=409,
            detail="Referenced monitoring station is missing",
        )

    pm25 = float(station.pm25)

    return {
        **_to_dict(route),
        "pm25": pm25,
        "exposure_score": round(
            pm25 * route.duration_min, 2
        ),
    }


def get_route_exposure(route_id: int, db: Session) -> dict:
    route = _get_existing_route(route_id, db)
    return _with_exposure(route, db)


def compare_routes(start: str, end: str, db: Session) -> dict:
    start, end = start.strip(), end.strip()

    if not start or not end:
        raise HTTPException(
            status_code=422,
            detail="Start and end cannot be empty",
        )

    if start.casefold() == end.casefold():
        raise HTTPException(
            status_code=422,
            detail="Start and end cannot be the same",
        )

    all_routes = db.scalars(select(Route)).all()

    matching = [
        _with_exposure(route, db)
        for route in all_routes
        if route.start.casefold() == start.casefold()
        and route.end.casefold() == end.casefold()
    ]

    if not matching:
        raise HTTPException(
            status_code=404,
            detail="No routes between these locations",
        )

    fastest = min(
        matching,
        key=lambda r: (
            r["duration_min"],
            r["exposure_score"],
            r["id"],
        ),
    )

    cleanest = min(
        matching,
        key=lambda r: (
            r["exposure_score"],
            r["duration_min"],
            r["id"],
        ),
    )

    return {
        "start": start,
        "end": end,
        "total_routes": len(matching),
        "fastest": fastest,
        "cleanest": cleanest,
    }
