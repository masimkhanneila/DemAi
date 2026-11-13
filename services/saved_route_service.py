from threading import Lock

from fastapi import HTTPException, status

from schemas.saved_route import SavedRouteCreate, SavedRouteUpdate
from store import routes, saved_routes, stations


_saved_routes_lock = Lock()


def _get_saved_route(saved_route_id: int) -> dict:
    saved_route = saved_routes.get(saved_route_id)
    if saved_route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Saved route not found"
        )
    return saved_route


def _with_exposure(saved_route: dict) -> dict:
    route = routes.get(saved_route["route_id"])
    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Route not found"
        )

    station = stations.get(route["station_id"])
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Referenced monitoring station is missing",
        )

    exposure_score = round(float(station["pm25"]) * route["duration_min"], 2)
    return {**saved_route, "exposure_score": exposure_score}


def _save(saved_route: dict) -> dict:
    response = _with_exposure(saved_route)
    saved_route_id = saved_route["id"]
    if any(
        existing["user_id"] == saved_route["user_id"]
        and existing["route_id"] == saved_route["route_id"]
        for existing_id, existing in saved_routes.items()
        if existing_id != saved_route_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This route is already saved by the user",
        )

    saved_routes[saved_route_id] = saved_route
    return response


def create_saved_route(payload: SavedRouteCreate) -> dict:
    with _saved_routes_lock:
        saved_route_id = max(saved_routes, default=0) + 1
        return _save({"id": saved_route_id, **payload.model_dump()})


def list_saved_routes() -> list[dict]:
    with _saved_routes_lock:
        return [_with_exposure(saved_route) for saved_route in saved_routes.values()]


def get_saved_route(saved_route_id: int) -> dict:
    with _saved_routes_lock:
        return _with_exposure(_get_saved_route(saved_route_id))


def update_saved_route(saved_route_id: int, payload: SavedRouteUpdate) -> dict:
    with _saved_routes_lock:
        saved_route = _get_saved_route(saved_route_id)
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide a field to update",
            )
        return _save({**saved_route, **changes})


def delete_saved_route(saved_route_id: int) -> None:
    with _saved_routes_lock:
        _get_saved_route(saved_route_id)
        del saved_routes[saved_route_id]