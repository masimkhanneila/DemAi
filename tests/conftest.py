"""Shared PostgreSQL fixtures; every test rolls back its own transaction."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from database import get_db
from main import app
from models.station import Station
from models.user import User
from security import create_access_token, hash_password


@pytest.fixture(scope="session")
def test_engine():
    dev_url = make_url(os.environ["DATABASE_URL"])
    if dev_url.get_backend_name() != "postgresql" or dev_url.database != "demai_db":
        raise RuntimeError("Tests expect DATABASE_URL to point to PostgreSQL demai_db")

    engine = create_engine(dev_url.set(database="demai_test_db"))
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(test_engine):
    with test_engine.connect() as connection:
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
            if transaction.is_active:
                transaction.rollback()


@pytest.fixture(scope="session")
def account_password_hash():
    return hash_password("AuthorizationTest_2026!")


@pytest.fixture
def accounts(db_session, account_password_hash):
    users = {
        "user": User(
            email="owner.authorization@example.com",
            hashed_password=account_password_hash,
            role="user",
        ),
        "other": User(
            email="other.authorization@example.com",
            hashed_password=account_password_hash,
            role="user",
        ),
        "admin": User(
            email="admin.authorization@example.com",
            hashed_password=account_password_hash,
            role="admin",
        ),
    }
    db_session.add_all(users.values())
    db_session.flush()
    return users


@pytest.fixture
def auth_headers(accounts):
    return {
        name: {"Authorization": f"Bearer {create_access_token(user.id)}"}
        for name, user in accounts.items()
    }


@pytest.fixture
def station_ids(db_session):
    first = Station(name="Medeu", location="Almaty", pm25=80)
    second = Station(name="Center", location="Almaty", pm25=20)
    db_session.add_all([first, second])
    db_session.flush()
    return first.id, second.id


@pytest.fixture
def api_client(db_session):
    def override_get_db():
        yield db_session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.fixture
def client(api_client, auth_headers, station_ids):
    """The existing route regression tests perform writes as an actual admin."""
    api_client.headers.update(auth_headers["admin"])
    return api_client
