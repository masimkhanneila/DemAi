# DemAI — Eco-Friendly Route Recommendation API

**Assignment 6 | FastAPI · PostgreSQL · SQLAlchemy · Alembic**

DemAI is a REST API for managing air-quality monitoring stations, walking routes, and saved routes. It compares alternative routes by travel duration and an estimated pollution-exposure score.

**Status:** Assignment 6 implementation completed. The API uses persistent PostgreSQL storage instead of the in-memory dictionaries from Assignment 5. The route test suite contains **19 passing tests** (verified locally by the team).

> **Scope:** This is a university proof of concept. Station PM2.5 values are provided through the API; DemAI does not retrieve live pollution readings or navigation directions from external services.

## Features

- **Monitoring stations:** Create, list, retrieve, update, and delete stations; classify air quality from PM2.5 readings.
- **Routes:** Manage routes, calculate their exposure scores, and compare the fastest and cleanest options between two locations.
- **Saved routes:** Save routes with a label and preference (`fastest` or `cleanest`); prevent a user from saving the same route twice.
- **Data integrity:** Validate API input and enforce primary keys, foreign keys, check constraints, and a uniqueness constraint in PostgreSQL.
- **Persistence:** Keep records after the FastAPI application restarts. Use Alembic to reproduce the database schema.

## Technology stack

| Component | Technology |
| --- | --- |
| API framework | FastAPI |
| Request/response validation | Pydantic v2 |
| Database | PostgreSQL |
| Object-relational mapping | SQLAlchemy ORM 2.x |
| PostgreSQL driver | Psycopg 3 |
| Database migrations | Alembic |
| Automated API testing | pytest and FastAPI TestClient |
| API documentation | Swagger UI (`/docs`) |

## Database design

```text
stations (1) ─────< (many) routes (1) ─────< (many) saved_routes
    id (PK)                  id (PK)                 id (PK)
                             station_id (FK)        route_id (FK)
```

| Table | Important fields | Constraints |
| --- | --- | --- |
| `stations` | `id`, `name`, `location`, `pm25` | Primary key; `pm25 >= 0`; required fields |
| `routes` | `id`, `start`, `end`, `distance_km`, `duration_min`, `station_id` | Primary key; foreign key to stations; positive distance and duration |
| `saved_routes` | `id`, `user_id`, `route_id`, `label`, `preference` | Primary key; foreign key to routes; unique (`user_id`, `route_id`); allowed preferences and nonblank label |

A station can have many routes; a route can appear in many saved-route records. Deletion of a referenced station or route is restricted, and the API returns **409 Conflict** for these cases. The `user_id` field is an integer identifier; this project does not implement a separate Users table or authentication.

### Air-quality and route calculations

Air quality is calculated from a station's current PM2.5 value:

| PM2.5 | Air quality |
| --- | --- |
| Below 15 | `low` |
| 15 to below 35 | `moderate` |
| 35 or above | `high` |

A route's simplified exposure score is:

```text
exposure_score = round(station.pm25 * route.duration_min, 2)
```

For routes with the same start and end, DemAI selects:

- **Fastest:** lowest duration, breaking ties by exposure score and then route ID.
- **Cleanest:** lowest exposure score, breaking ties by duration and then route ID.

The score is recalculated using the latest station reading. It is a simplified comparison metric, **not a medically precise exposure measurement**.

## API endpoints

| Resource | Method | Endpoint | Purpose |
| --- | --- | --- | --- |
| Health | GET | `/` | Application status |
| Stations | POST | `/stations` | Create a station |
| Stations | GET | `/stations` | List stations |
| Stations | GET | `/stations/{station_id}` | Retrieve a station |
| Stations | PATCH | `/stations/{station_id}` | Update a station |
| Stations | DELETE | `/stations/{station_id}` | Delete a station |
| Routes | POST | `/routes` | Create a route |
| Routes | GET | `/routes` | List routes |
| Routes | GET | `/routes/{route_id}` | Retrieve a route |
| Routes | PATCH | `/routes/{route_id}` | Update a route |
| Routes | DELETE | `/routes/{route_id}` | Delete a route |
| Routes | GET | `/routes/{route_id}/exposure` | Calculate route exposure |
| Routes | GET | `/routes/compare?start=...&end=...` | Compare fastest and cleanest routes |
| Saved routes | POST | `/saved-routes` | Save a route |
| Saved routes | GET | `/saved-routes` | List saved routes |
| Saved routes | GET | `/saved-routes/{saved_route_id}` | Retrieve a saved route |
| Saved routes | PATCH | `/saved-routes/{saved_route_id}` | Update a saved route |
| Saved routes | DELETE | `/saved-routes/{saved_route_id}` | Remove a saved route |

Typical responses use **200 OK** for reads/updates, **201 Created** for creation, and **204 No Content** for deletion. The API uses **404** for missing resources, **409** for conflicts, and **422** for invalid input.

## Getting started (Windows PowerShell)

### 1. Clone the repository and install dependencies

Requirements: Python, PostgreSQL running locally (default port `5432`), and Git.

```powershell
git clone https://github.com/masimkhanneila/DemAi.git
cd DemAi
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Create the PostgreSQL database

In pgAdmin, create a database called **`demai_db`**, or run this SQL while connected to a different database with permission to create databases:

```sql
CREATE DATABASE demai_db;
```

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Edit `.env` to use a PostgreSQL account with access to `demai_db`:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/demai_db
```

Replace `YOUR_PASSWORD` with your own credentials. If your password contains reserved URL characters (for example `@` or `#`), percent-encode them. **Never commit or share `.env`**; it is excluded by `.gitignore`.

### 3. Apply database migrations

```powershell
python -m alembic upgrade head
python -m alembic current
```

The initial Alembic migration creates `stations`, `routes`, and `saved_routes`; Alembic also maintains its own `alembic_version` table. No manual SQL table creation is needed.

### 4. Run the API

```powershell
python -m uvicorn main:app --reload
```

Open:

- **Swagger UI:** http://127.0.0.1:8000/docs
- **OpenAPI specification:** http://127.0.0.1:8000/openapi.json
- **Health endpoint:** http://127.0.0.1:8000/

## Example workflow

Try these requests in Swagger UI, in order. Use the IDs returned by previous requests rather than assuming a record's ID.

**1. Create a monitoring station — `POST /stations`**

```json
{
  "name": "Medeu",
  "location": "Almaty",
  "pm25": 80
}
```

**2. Create a route — `POST /routes`**

```json
{
  "start": "Medeu",
  "end": "Center",
  "distance_km": 2.3,
  "duration_min": 15,
  "station_id": 1
}
```

Replace `station_id` with the actual station ID returned in step 1.

**3. Check exposure — `GET /routes/{route_id}/exposure`**

For PM2.5 = 80 and a 15-minute duration, the calculated score is `1200`.

**4. Compare routes — `GET /routes/compare?start=Medeu&end=Center`**

Create at least two routes with those endpoints to compare alternatives.

**5. Save a route — `POST /saved-routes`**

```json
{
  "user_id": 1,
  "route_id": 1,
  "label": "My walking route",
  "preference": "cleanest"
}
```

Replace `route_id` with the route ID from step 2. Saving the same route twice for the same user returns a conflict.

## Automated testing

The route suite contains **19 pytest tests**, covering CRUD behavior, input validation, missing resources, exposure recalculation, route comparison, and deletion conflicts. It uses a **separate PostgreSQL database** and rolls back test changes after each test.

### 1. Create a dedicated test database

In pgAdmin, create **`demai_test_db`** using the same PostgreSQL server credentials. **Do not run tests against `demai_db`**: the test suite intentionally targets a separate database.

### 2. Initialize the test database schema

From the project root, with your working `.env` configured for `demai_db`, execute:

```powershell
python -c "import os; from dotenv import load_dotenv; from sqlalchemy.engine import make_url; from alembic import command; from alembic.config import Config; load_dotenv(); u=make_url(os.environ['DATABASE_URL']); assert u.database == 'demai_db'; os.environ['DATABASE_URL']=u.set(database='demai_test_db').render_as_string(hide_password=False); command.upgrade(Config('alembic.ini'), 'head')"
```

This applies the existing migration to `demai_test_db` without changing your development database configuration.

### 3. Run the tests

```powershell
python -m pytest tests/test_routes.py -v
```

**Locally verified result:** `19 passed`.

**Note:** The current test configuration expects the development database name `demai_db` and derives the test connection by changing only its database name to `demai_test_db`. Both databases must be accessible with the same credentials.

## Project structure

```text
DemAi/
├── main.py                    # FastAPI application and routers
├── database.py                # Engine, session factory, Base, get_db
├── models/                    # SQLAlchemy table definitions
│   ├── __init__.py
│   ├── station.py
│   ├── route.py
│   └── saved_route.py
├── schemas/                   # Pydantic request/response models
├── routers/                   # HTTP endpoints
├── services/                  # Database operations and business rules
├── alembic/
│   ├── env.py                 # Migration configuration
│   └── versions/              # Versioned migration scripts
├── alembic.ini
├── tests/
│   └── test_routes.py
├── requirements.txt
├── .env.example
├── TEAM_TASKS.md
└── README.md
```

## Team contributions

This project was developed by a three-person team:

| Responsibility | Scope |
| --- | --- |
| Member 1 — Stations | Station ORM model, station services and endpoints |
| Member 2 — Routes / team leader | Route ORM model, route services and endpoints, shared database foundation, migrations, integration and tests |
| Member 3 — Saved routes | SavedRoute ORM model, saved-route services and endpoints |

Changes were developed in feature branches and integrated through GitHub pull requests.

## Assignment 5 → Assignment 6

| Assignment 5 | Assignment 6 |
| --- | --- |
| In-memory Python dictionaries | Persistent PostgreSQL tables |
| Manual record ID management | Database-generated primary keys |
| Application-only relationship checks | Foreign key and relational constraints |
| Data lost when the server restarts | Records persist across restarts |
| No schema migrations | Version-controlled Alembic migrations |
| Dictionary-based tests | Database-backed pytest tests |

**Repository:** https://github.com/masimkhanneila/DemAi
