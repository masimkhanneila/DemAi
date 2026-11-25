from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from models.route import Route
from models.saved_route import SavedRoute
from models.station import Station
from models.user import User
from security import ALGORITHM, SECRET_KEY


@pytest.fixture
def route_ids(db_session, station_ids):
    routes = [
        Route(start="Medeu", end="Center", distance_km=2.3,
              duration_min=15, station_id=station_ids[0]),
        Route(start="Medeu", end="Center", distance_km=3.0,
              duration_min=25, station_id=station_ids[1]),
    ]
    db_session.add_all(routes)
    db_session.flush()
    return routes[0].id, routes[1].id


@pytest.fixture
def private_routes(db_session, accounts, route_ids):
    records = {
        name: SavedRoute(
            user_id=user.id, route_id=route_ids[0],
            label=f"{name}'s route", preference="fastest",
        )
        for name, user in accounts.items()
    }
    db_session.add_all(records.values())
    db_session.flush()
    return records


def saved_payload(route_id, **changes):
    return {"route_id": route_id, "label": "My route",
            "preference": "fastest", **changes}


def public_state(db):
    return (
        db.execute(select(Station.id, Station.name, Station.location, Station.pm25)
                   .order_by(Station.id)).all(),
        db.execute(select(Route.id, Route.start, Route.end, Route.distance_km,
                          Route.duration_min, Route.station_id)
                   .order_by(Route.id)).all(),
    )


def private_state(db):
    return db.execute(
        select(SavedRoute.id, SavedRoute.user_id, SavedRoute.route_id,
               SavedRoute.label, SavedRoute.preference).order_by(SavedRoute.id)
    ).all()


@pytest.mark.parametrize("actor", [None, "user", "admin"])
def test_station_route_reads_and_comparison_are_public(
    api_client, station_ids, route_ids, auth_headers, actor,
):
    headers = auth_headers[actor] if actor else {}
    paths = [
        "/stations", f"/stations/{station_ids[0]}",
        "/routes", f"/routes/{route_ids[0]}",
        f"/routes/{route_ids[0]}/exposure",
        "/routes/compare?start=Medeu&end=Center",
    ]
    responses = [api_client.get(path, headers=headers) for path in paths]
    assert [response.status_code for response in responses] == [200] * len(paths)
    assert {item["id"] for item in responses[0].json()} == set(station_ids)
    assert {item["id"] for item in responses[2].json()} == set(route_ids)
    assert responses[4].json()["exposure_score"] == 1200
    assert responses[5].json()["fastest"]["id"] == route_ids[0]
    assert responses[5].json()["cleanest"]["id"] == route_ids[1]


@pytest.mark.parametrize("actor,expected", [(None, 401), ("user", 403)])
@pytest.mark.parametrize("resource", ["stations", "routes"])
@pytest.mark.parametrize("method", ["post", "patch", "delete"])
def test_public_resource_writes_require_admin(
    api_client, db_session, auth_headers, station_ids, route_ids,
    actor, expected, resource, method,
):
    unused = Station(name="Unused", location="Almaty", pm25=10)
    db_session.add(unused)
    db_session.flush()
    if resource == "stations":
        target_id = unused.id if method == "delete" else station_ids[0]
        payload = ({"name": "New station", "location": "Almaty", "pm25": 15}
                   if method == "post" else {"pm25": 15})
    else:
        target_id = route_ids[0]
        payload = ({"start": "Campus", "end": "Home", "distance_km": 3,
                    "duration_min": 10, "station_id": station_ids[0]}
                   if method == "post" else {"duration_min": 20})
    path = f"/{resource}" if method == "post" else f"/{resource}/{target_id}"
    before = public_state(db_session)
    response = api_client.request(
        method, path, json=payload if method != "delete" else None,
        headers=auth_headers[actor] if actor else {},
    )
    assert response.status_code == expected
    if expected == 401:
        assert response.headers["www-authenticate"] == "Bearer"
    assert public_state(db_session) == before


def test_admin_can_manage_stations_and_routes(api_client, auth_headers):
    headers = auth_headers["admin"]
    station = api_client.post("/stations", headers=headers, json={
        "name": "Admin station", "location": "Almaty", "pm25": 20,
    })
    assert station.status_code == 201
    station_id = station.json()["id"]
    updated = api_client.patch(f"/stations/{station_id}", headers=headers,
                               json={"pm25": 10})
    assert updated.status_code == 200
    assert updated.json()["pm25"] == 10
    route = api_client.post("/routes", headers=headers, json={
        "start": "Campus", "end": "Home", "distance_km": 3,
        "duration_min": 10, "station_id": station_id,
    })
    assert route.status_code == 201
    route_id = route.json()["id"]
    updated = api_client.patch(f"/routes/{route_id}", headers=headers,
                               json={"duration_min": 20})
    assert updated.status_code == 200
    assert updated.json()["duration_min"] == 20
    assert api_client.delete(f"/routes/{route_id}", headers=headers).status_code == 204
    assert api_client.get(f"/routes/{route_id}").status_code == 404
    assert api_client.delete(f"/stations/{station_id}", headers=headers).status_code == 204
    assert api_client.get(f"/stations/{station_id}").status_code == 404


@pytest.mark.parametrize("operation", ["list", "get", "create", "patch", "delete"])
def test_all_saved_route_endpoints_require_authentication(
    api_client, db_session, private_routes, route_ids, operation,
):
    path = f"/saved-routes/{private_routes['user'].id}"
    requests = {
        "list": ("get", "/saved-routes", None),
        "get": ("get", path, None),
        "create": ("post", "/saved-routes", saved_payload(route_ids[1])),
        "patch": ("patch", path, {"label": "Unauthorized"}),
        "delete": ("delete", path, None),
    }
    method, path, payload = requests[operation]
    before = private_state(db_session)
    response = api_client.request(method, path, json=payload)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert private_state(db_session) == before


@pytest.mark.parametrize("kind", ["malformed", "wrong_signature", "expired", "unknown_user"])
def test_invalid_tokens_cannot_access_saved_routes_or_admin_actions(
    api_client, db_session, accounts, kind,
):
    claims = {
        "sub": str(accounts["user"].id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    if kind == "expired":
        claims["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    elif kind == "unknown_user":
        claims["sub"] = str(max(user.id for user in accounts.values()) + 1_000_000)
    key = f"{SECRET_KEY}-wrong" if kind == "wrong_signature" else SECRET_KEY
    token = "not-a-jwt" if kind == "malformed" else jwt.encode(claims, key, algorithm=ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}
    before = public_state(db_session), private_state(db_session)
    responses = [
        api_client.get("/saved-routes", headers=headers),
        api_client.post("/stations", headers=headers, json={
            "name": "Invalid token", "location": "Almaty", "pm25": 10,
        }),
    ]
    for response in responses:
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
    assert (public_state(db_session), private_state(db_session)) == before


@pytest.mark.parametrize("actor", ["user", "other", "admin"])
def test_authenticated_owner_can_manage_only_their_saved_routes(
    api_client, db_session, accounts, auth_headers, private_routes, route_ids,
    station_ids, actor,
):
    headers = auth_headers[actor]
    response = api_client.post("/saved-routes", headers=headers,
                               json=saved_payload(route_ids[1], label="  My walk  "))
    assert response.status_code == 201
    record = response.json()
    assert record["user_id"] == accounts[actor].id
    assert record["label"] == "My walk"
    assert record["exposure_score"] == 500
    path = f"/saved-routes/{record['id']}"
    assert api_client.get(path, headers=headers).json() == record
    listed = api_client.get("/saved-routes", headers=headers)
    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()} == {private_routes[actor].id, record["id"]}
    assert all(item["user_id"] == accounts[actor].id for item in listed.json())
    updated = api_client.patch(path, headers=headers, json={
        "label": "Updated walk", "preference": "cleanest",
    })
    assert updated.status_code == 200
    assert updated.json()["label"] == "Updated walk"
    assert updated.json()["preference"] == "cleanest"
    assert updated.json()["user_id"] == accounts[actor].id
    station = db_session.get(Station, station_ids[1])
    station.pm25 = 10
    db_session.commit()
    assert api_client.get(path, headers=headers).json()["exposure_score"] == 250
    deleted = api_client.delete(path, headers=headers)
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert api_client.get(path, headers=headers).status_code == 404
    assert {item["id"] for item in api_client.get("/saved-routes", headers=headers).json()} == {
        private_routes[actor].id,
    }
    for name, other_record in private_routes.items():
        if name != actor:
            assert db_session.get(SavedRoute, other_record.id) is not None


@pytest.mark.parametrize("actor", ["other", "admin"])
@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_other_owners_and_admins_cannot_access_a_private_saved_route(
    api_client, db_session, auth_headers, private_routes, actor, method,
):
    record_id = private_routes["user"].id
    missing_id = max(record.id for record in private_routes.values()) + 1_000_000
    before = private_state(db_session)
    payload = {"label": "Unauthorized change"} if method == "patch" else None
    forbidden = api_client.request(method, f"/saved-routes/{record_id}",
                                    headers=auth_headers[actor], json=payload)
    missing = api_client.request(method, f"/saved-routes/{missing_id}",
                                 headers=auth_headers[actor], json=payload)
    assert forbidden.status_code == missing.status_code == 404
    assert forbidden.json() == missing.json() == {"detail": "Saved route not found"}
    assert private_state(db_session) == before


def test_list_cannot_be_redirected_to_another_owner(api_client, accounts, auth_headers, private_routes):
    response = api_client.get("/saved-routes", headers=auth_headers["user"],
                               params={"user_id": accounts["other"].id})
    assert response.status_code == 200
    assert [record["id"] for record in response.json()] == [private_routes["user"].id]


@pytest.mark.parametrize("method", ["post", "patch"])
def test_client_cannot_supply_or_change_saved_route_owner(
    api_client, db_session, accounts, auth_headers, private_routes, route_ids, method,
):
    payload = {"user_id": accounts["other"].id, "label": "Forged owner"}
    path = f"/saved-routes/{private_routes['user'].id}"
    if method == "post":
        path = "/saved-routes"
        payload = saved_payload(route_ids[1], **payload)
    before = private_state(db_session)
    response = api_client.request(method, path, headers=auth_headers["user"], json=payload)
    assert response.status_code == 422
    assert any(error["loc"] == ["body", "user_id"] and error["type"] == "extra_forbidden"
               for error in response.json()["detail"])
    assert private_state(db_session) == before


def test_saved_route_uniqueness_is_per_owner(api_client, auth_headers, route_ids):
    payload = saved_payload(route_ids[0])
    first = api_client.post("/saved-routes", headers=auth_headers["user"], json=payload)
    assert first.status_code == 201
    duplicate = api_client.post("/saved-routes", headers=auth_headers["user"], json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "This route is already saved by the user"
    other = api_client.post("/saved-routes", headers=auth_headers["other"], json=payload)
    assert other.status_code == 201
    assert other.json()["user_id"] != first.json()["user_id"]
    after_rollback = api_client.post("/saved-routes", headers=auth_headers["user"],
                                      json=saved_payload(route_ids[1]))
    assert after_rollback.status_code == 201


@pytest.mark.parametrize("payload", [{}, {"label": None}, {"preference": None}])
def test_saved_route_update_validation_is_preserved(api_client, auth_headers, private_routes, payload):
    response = api_client.patch(f"/saved-routes/{private_routes['user'].id}",
                                 headers=auth_headers["user"], json=payload)
    assert response.status_code == 422


def test_public_registration_cannot_grant_admin_role(api_client, db_session):
    credentials = {"email": "registration.authorization@example.com", "password": "RegistrationTest_2026!"}
    registered = api_client.post("/auth/register", json={**credentials, "role": "admin"})
    assert registered.status_code == 201
    assert registered.json()["role"] == "user"
    assert db_session.get(User, registered.json()["id"]).role == "user"
    logged_in = api_client.post("/auth/login", json=credentials)
    assert logged_in.status_code == 200
    headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}
    denied = api_client.post("/stations", headers=headers, json={
        "name": "Escalation attempt", "location": "Almaty", "pm25": 10,
    })
    assert denied.status_code == 403


def test_downgrading_admin_revokes_admin_actions(api_client, db_session, accounts, auth_headers):
    accounts["admin"].role = "user"
    db_session.commit()
    response = api_client.post("/stations", headers=auth_headers["admin"], json={
        "name": "Former admin", "location": "Almaty", "pm25": 10,
    })
    assert response.status_code == 403
    assert api_client.get("/saved-routes", headers=auth_headers["admin"]).status_code == 200


def test_saved_route_foreign_key_rejects_a_nonexistent_owner(db_session, accounts, route_ids):
    missing_user_id = max(user.id for user in accounts.values()) + 1_000_000
    with pytest.raises(IntegrityError) as error:
        with db_session.begin_nested():
            db_session.add(SavedRoute(user_id=missing_user_id, **saved_payload(route_ids[0])))
            db_session.flush()
    assert error.value.orig.sqlstate == "23503"
    assert error.value.orig.diag.constraint_name == "fk_saved_routes_user_id_users"


def test_saved_route_foreign_key_restricts_deleting_its_owner(db_session, private_routes):
    owner_id = private_routes["user"].user_id
    with pytest.raises(IntegrityError) as error:
        with db_session.begin_nested():
            db_session.execute(delete(User).where(User.id == owner_id))
    assert error.value.orig.sqlstate == "23503"
    assert error.value.orig.diag.constraint_name == "fk_saved_routes_user_id_users"
