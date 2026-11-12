from fastapi import HTTPException, status
from pydantic import ValidationError

from schemas.route import RouteCreate, RouteUpdate
from store import routes, stations, saved_routes


def _check_station(station_id: int) -> None:
    if station_id not in stations:
        raise HTTPException(status_code=404, detail="Monitoring station not found")


def list_routes() -> list[dict]:
    return list(routes.values())


def get_route(route_id: int) -> dict:
    route = routes.get(route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


def create_route(payload: RouteCreate) -> dict:
    _check_station(payload.station_id)
    route_id = max(routes.keys(), default=0) + 1
    route = {"id": route_id, **payload.model_dump()}
    routes[route_id] = route
    return route


def update_route(route_id: int, payload: RouteUpdate) -> dict:
    existing = get_route(route_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Provide a field to update")

    updated = {**existing, **changes}
    # Validate the complete result, not just the fields sent in PATCH.
    try:
        validated = RouteCreate.model_validate(updated)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_context=False, include_url=False),
        ) from exc
    _check_station(validated.station_id)

    route = {"id": route_id, **validated.model_dump()}
    routes[route_id] = route
    return route


def delete_route(route_id: int) -> None:
    get_route(route_id)
    if any(saved["route_id"] == route_id for saved in saved_routes.values()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a route that is saved by a user",
        )
    del routes[route_id]


def get_route_exposure(route_id: int) -> dict:
    route = get_route(route_id)
    station = stations.get(route["station_id"])
    if station is None:
        raise HTTPException(
            status_code=409, detail="Referenced monitoring station is missing"
        )
    pm25 = float(station["pm25"])
    return {
        **route,
        "pm25": pm25,
        # Simplified educational comparison score, not a medical exposure estimate.
        "exposure_score": round(pm25 * route["duration_min"], 2),
    }


def compare_routes(start: str, end: str) -> dict:
    start, end = start.strip(), end.strip()
    if not start or not end:
        raise HTTPException(status_code=422, detail="Start and end cannot be empty")
    if start.casefold() == end.casefold():
        raise HTTPException(status_code=422, detail="Start and end cannot be the same")

    matching = [
        get_route_exposure(route["id"])
        for route in routes.values()
        if route["start"].casefold() == start.casefold()
        and route["end"].casefold() == end.casefold()
    ]
    if not matching:
        raise HTTPException(status_code=404, detail="No routes between these locations")

    fastest = min(matching, key=lambda r: (r["duration_min"], r["exposure_score"], r["id"]))
    cleanest = min(matching, key=lambda r: (r["exposure_score"], r["duration_min"], r["id"]))
    return {
        "start": start,
        "end": end,
        "total_routes": len(matching),
        "fastest": fastest,
        "cleanest": cleanest,
    }
