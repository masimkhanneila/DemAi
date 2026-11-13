import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.routes import router
from store import routes, saved_routes, stations

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_store():
    stations.clear()
    routes.clear()
    saved_routes.clear()
    stations[1] = {"id": 1, "name": "Medeu", "location": "Almaty", "pm25": 80}
    stations[2] = {"id": 2, "name": "Center", "location": "Almaty", "pm25": 20}
    yield
    stations.clear()
    routes.clear()
    saved_routes.clear()


def route_payload(**changes):
    payload = {"start": "Medeu", "end": "Center", "distance_km": 2.3, "duration_min": 15, "station_id": 1}
    payload.update(changes)
    return payload


def create(**changes):
    return client.post("/routes", json=route_payload(**changes))


def test_create_route():
    response = create()
    assert response.status_code == 201
    assert response.json()["id"] == 1
    assert routes[1]["station_id"] == 1


def test_list_and_get_route():
    create()
    assert len(client.get("/routes").json()) == 1
    assert client.get("/routes/1").json()["start"] == "Medeu"


def test_missing_route():
    assert client.get("/routes/999").status_code == 404


def test_missing_station():
    assert create(station_id=500).status_code == 404


def test_invalid_distance():
    assert create(distance_km=-1).status_code == 422


def test_invalid_duration():
    assert create(duration_min=0).status_code == 422


def test_empty_location():
    assert create(start="  ").status_code == 422


def test_same_location():
    assert create(start=" Medeu ", end="medeu").status_code == 422


def test_patch_route():
    create()
    response = client.patch("/routes/1", json={"duration_min": 25})
    assert response.status_code == 200
    assert response.json()["duration_min"] == 25


def test_patch_conflicting_start():
    create()
    assert client.patch("/routes/1", json={"start": "Center"}).status_code == 422


def test_patch_null_rejected():
    create()
    assert client.patch("/routes/1", json={"start": None}).status_code == 422


def test_patch_empty_rejected():
    create()
    assert client.patch("/routes/1", json={}).status_code == 422


def test_patch_nonexistent_station():
    create()
    assert client.patch("/routes/1", json={"station_id": 100}).status_code == 404


def test_exposure_uses_latest_pm25():
    create()
    assert client.get("/routes/1/exposure").json()["exposure_score"] == 1200
    stations[1]["pm25"] = 10
    assert client.get("/routes/1/exposure").json()["exposure_score"] == 150


def test_compare_fastest_and_cleanest():
    create()
    create(duration_min=25, station_id=2)
    response = client.get("/routes/compare", params={"start": " MEDEU ", "end": "center"})
    assert response.status_code == 200
    result = response.json()
    assert result["total_routes"] == 2
    assert result["fastest"]["id"] == 1
    assert result["cleanest"]["id"] == 2


def test_compare_unavailable():
    assert client.get("/routes/compare", params={"start": "A", "end": "B"}).status_code == 404


def test_delete():
    create()
    assert client.delete("/routes/1").status_code == 204
    assert client.get("/routes/1").status_code == 404


def test_delete_saved_route_conflict():
    create()
    saved_routes[1] = {"id": 1, "user_id": 1, "route_id": 1, "label": "Walk", "preference": "cleanest"}
    assert client.delete("/routes/1").status_code == 409


def test_delete_nonexistent_route():
    assert client.delete("/routes/99").status_code == 404
