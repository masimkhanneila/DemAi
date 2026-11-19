
import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from database import get_db
from main import app
from models.route import Route
from models.saved_route import SavedRoute
from models.station import Station


# Always use a separate PostgreSQL database for testing.
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing")

main_url = make_url(DATABASE_URL)

if main_url.database != "demai_db":
    raise RuntimeError("Unexpected development database")

# Same credentials, but a different database
test_url = main_url.set(database="demai_test_db")

test_engine = create_engine(test_url)


@pytest.fixture
def db_session():
    connection = test_engine.connect()
    transaction = connection.begin()

    db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def station_ids(db_session):
    first = Station(
        name="Medeu",
        location="Almaty",
        pm25=80,
    )
    second = Station(
        name="Center",
        location="Almaty",
        pm25=20,
    )

    db_session.add_all([first, second])
    db_session.flush()

    return first.id, second.id


@pytest.fixture
def client(db_session, station_ids):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def route_payload(station_id, **changes):
    payload = {
        "start": "Medeu",
        "end": "Center",
        "distance_km": 2.3,
        "duration_min": 15,
        "station_id": station_id,
    }
    payload.update(changes)
    return payload


def create(client, station_id, **changes):
    return client.post(
        "/routes",
        json=route_payload(station_id, **changes),
    )


# ---------- CREATE ----------

def test_create_route(client, station_ids, db_session):
    response = create(client, station_ids[0])

    assert response.status_code == 201

    route_id = response.json()["id"]
    route = db_session.get(Route, route_id)

    assert route is not None
    assert route.station_id == station_ids[0]


def test_list_and_get_route(client, station_ids):
    response = create(client, station_ids[0])
    route_id = response.json()["id"]

    listed = client.get("/routes")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    retrieved = client.get(f"/routes/{route_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["start"] == "Medeu"


# ---------- NOT FOUND ----------

def test_missing_route(client):
    response = client.get("/routes/999999")
    assert response.status_code == 404


def test_missing_station(client):
    response = create(client, 999999)
    assert response.status_code == 404


# ---------- VALIDATION ----------

def test_invalid_distance(client, station_ids):
    response = create(
        client, station_ids[0], distance_km=-1
    )
    assert response.status_code == 422


def test_invalid_duration(client, station_ids):
    response = create(
        client, station_ids[0], duration_min=0
    )
    assert response.status_code == 422


def test_empty_location(client, station_ids):
    response = create(
        client, station_ids[0], start="  "
    )
    assert response.status_code == 422


def test_same_location(client, station_ids):
    response = create(
        client,
        station_ids[0],
        start=" Medeu ",
        end="medeu",
    )
    assert response.status_code == 422


# ---------- UPDATE ----------

def test_patch_route(client, station_ids):
    created = create(client, station_ids[0])
    route_id = created.json()["id"]

    response = client.patch(
        f"/routes/{route_id}",
        json={"duration_min": 25},
    )

    assert response.status_code == 200
    assert response.json()["duration_min"] == 25


def test_patch_conflicting_start(client, station_ids):
    created = create(client, station_ids[0])
    route_id = created.json()["id"]

    response = client.patch(
        f"/routes/{route_id}",
        json={"start": "Center"},
    )
    assert response.status_code == 422


def test_patch_null_rejected(client, station_ids):
    created = create(client, station_ids[0])
    route_id = created.json()["id"]

    response = client.patch(
        f"/routes/{route_id}",
        json={"start": None},
    )
    assert response.status_code == 422


def test_patch_empty_rejected(client, station_ids):
    created = create(client, station_ids[0])
    route_id = created.json()["id"]

    response = client.patch(
        f"/routes/{route_id}",
        json={},
    )
    assert response.status_code == 422


def test_patch_nonexistent_station(client, station_ids):
    created = create(client, station_ids[0])
    route_id = created.json()["id"]

    response = client.patch(
        f"/routes/{route_id}",
        json={"station_id": 999999},
    )
    assert response.status_code == 404


# ---------- EXPOSURE ----------

def test_exposure_uses_latest_pm25(
    client, station_ids, db_session
):
    created = create(client, station_ids[0])
    route_id = created.json()["id"]

    response = client.get(f"/routes/{route_id}/exposure")
    assert response.status_code == 200
    assert response.json()["exposure_score"] == 1200

    station = db_session.get(Station, station_ids[0])
    station.pm25 = 10
    db_session.commit()

    response = client.get(f"/routes/{route_id}/exposure")
    assert response.status_code == 200
    assert response.json()["exposure_score"] == 150


# ---------- COMPARISON ----------

def test_compare_fastest_and_cleanest(
    client, station_ids
):
    first = create(client, station_ids[0])
    second = create(
        client,
        station_ids[1],
        duration_min=25,
    )

    first_id = first.json()["id"]
    second_id = second.json()["id"]

    response = client.get(
        "/routes/compare",
        params={
            "start": " MEDEU ",
            "end": "center",
        },
    )

    assert response.status_code == 200

    result = response.json()
    assert result["total_routes"] == 2
    assert result["fastest"]["id"] == first_id
    assert result["cleanest"]["id"] == second_id


def test_compare_unavailable(client):
    response = client.get(
        "/routes/compare",
        params={"start": "A", "end": "B"},
    )
    assert response.status_code == 404


# ---------- DELETE ----------

def test_delete(client, station_ids):
    created = create(client, station_ids[0])
    route_id = created.json()["id"]

    response = client.delete(f"/routes/{route_id}")
    assert response.status_code == 204

    response = client.get(f"/routes/{route_id}")
    assert response.status_code == 404


def test_delete_saved_route_conflict(
    client, station_ids, db_session
):
    created = create(client, station_ids[0])
    route_id = created.json()["id"]

    saved = SavedRoute(
        user_id=1,
        route_id=route_id,
        label="Walk",
        preference="cleanest",
    )

    db_session.add(saved)
    db_session.commit()

    response = client.delete(f"/routes/{route_id}")
    assert response.status_code == 409


def test_delete_nonexistent_route(client):
    response = client.delete("/routes/999999")
    assert response.status_code == 404
