# DemAI — Eco-Friendly Route Recommendation REST API

> **Assignment 6: PostgreSQL persistence and relational data**  
> **Deadline:** November 20, 2026, 00:00 (the beginning of Friday).  
> **Status:** Migration from Assignment 5 is in progress. Do not assume the database-backed implementation is complete until the relevant branches are merged and tested.

## 1. Project overview

DemAI is a **student proof-of-concept REST API**, not a live navigation or pollution-measurement service. It manages air-quality monitoring stations, walking routes, and users' saved routes. It compares routes by **travel duration** and by a **simplified pollution exposure score**.

**Tech stack:** Python, FastAPI, Pydantic v2, PostgreSQL, SQLAlchemy ORM 2.x, Psycopg 3, Alembic, and pytest/Swagger UI.

### Assignment 5 → Assignment 6

| Assignment 5 (existing code) | Assignment 6 (target) |
| --- | --- |
| `store.py`: three in-memory dictionaries | Three PostgreSQL tables |
| Dictionary lookups and manual IDs | SQLAlchemy sessions and database-generated primary keys |
| Manual relationship checks only | Database foreign keys **plus** clear API errors |
| Data lost on restart | Data persists after server restart |
| No migrations | Alembic migrations committed to Git |

**Do not rewrite the API from scratch.** Keep the existing endpoints, Pydantic validation, and business logic wherever possible. Replace the storage implementation in the service layer.

## 2. Database fundamentals

- **PostgreSQL** stores persistent rows in relational tables.
- **SQLAlchemy ORM** maps Python model classes to those tables and lets services query or modify records through a `Session`.
- **Primary key (PK)** uniquely identifies a record (`id`).
- **Foreign key (FK)** references a record in another table and protects relationships.
- **One-to-many relationship:** one Station has many Routes; one Route has many SavedRoutes.
- **Alembic migration** is a versioned script that creates or changes the database schema. Migration files belong in Git; actual local data and credentials do not.
- **Pydantic schema ≠ SQLAlchemy model.** Pydantic validates API requests/responses; SQLAlchemy defines database tables and relationships.
- **Engine ≠ session.** The engine manages DB connectivity; a session is used by a request to perform reads and writes. Use the shared `get_db()` dependency to manage session lifetime.

### Relationship diagram

```text
stations (1) ──────< (many) routes (1) ──────< (many) saved_routes
    PK id                     PK id                        PK id
                              FK station_id → stations.id   FK route_id → routes.id
                                                            user_id (integer only; no Users table)
```

`user_id` is a simple integer retained from Assignment 5, **not** a foreign key to a nonexistent `users` table. Do not add authentication or a Users resource unless the whole team agrees to expand scope.

## 3. Agreed tables and constraints

These are the team's **target database contract**, not a claim that the tables already exist.

### `stations` — Member 1

| Column | SQL type | Requirements |
| --- | --- | --- |
| `id` | integer | PK, database-generated |
| `name` | varchar(100) | Not null, nonblank after trimming |
| `location` | varchar(100) | Not null, nonblank after trimming |
| `pm25` | double precision / float | Not null, `>= 0` |

One Station has many Routes (`Station.routes` / `Route.station`). **Do not store `air_quality` as a column**; compute it for API responses:

- `pm25 < 15` → `low`
- `15 <= pm25 < 35` → `moderate`
- `pm25 >= 35` → `high`

### `routes` — Member 2

| Column | SQL type | Requirements |
| --- | --- | --- |
| `id` | integer | PK, database-generated |
| `start` | varchar(100) | Not null, nonblank |
| `end` | varchar(100) | Not null, nonblank; different from start ignoring case |
| `distance_km` | double precision / float | Not null, `> 0`, finite |
| `duration_min` | integer | Not null, `> 0` |
| `station_id` | integer | Not null, FK → `stations.id`, restrictive delete |

A Route belongs to one Station and can have many SavedRoutes (`Route.saved_routes` / `SavedRoute.route`). Preserve the existing Pydantic validation including `.strip()`, `.casefold()`, no explicit null in PATCH, and whole-route validation after merging changes.

**Calculated, not stored:**

```text
exposure_score = round(station.pm25 * route.duration_min, 2)
```

This is a **simplified comparison score**, not a medically precise inhaled dose. For the same start and end:

- **Fastest:** `min(routes, key=(duration_min, exposure_score, id))`
- **Cleanest:** `min(routes, key=(exposure_score, duration_min, id))`

Use stable tie-breakers and preserve case-insensitive matching of start/end.

### `saved_routes` — Member 3

| Column | SQL type | Requirements |
| --- | --- | --- |
| `id` | integer | PK, database-generated |
| `user_id` | integer | Not null; existing pseudo-user identifier |
| `route_id` | integer | Not null, FK → `routes.id`, restrictive delete |
| `label` | varchar(100) | Not null, nonblank; align Pydantic length limit |
| `preference` | varchar(20) | Not null, `fastest` or `cleanest` |

**Unique constraint:** `(user_id, route_id)`. The same user must not save one route twice. Multiple users may save the same route. **Do not store `exposure_score`**; calculate it when returning saved routes using the latest Station PM2.5 and Route duration.

### Integrity and deletion policy

- Reference a nonexistent station or route → clear `404 Not Found` from the API.
- Delete a Station still referenced by a Route → `409 Conflict`.
- Delete a Route still referenced by a SavedRoute → `409 Conflict`.
- Duplicate saved route for one user → `409 Conflict`.
- Invalid data or empty PATCH → `422`.
- Enforce foreign keys, non-null values, appropriate CHECK constraints, and the saved-route uniqueness constraint in PostgreSQL **as well as** meaningful validation in application code.
- Use restrictive FK deletion (not cascade). If a database `IntegrityError` occurs, roll back the transaction and return an appropriate response rather than leaking a `500`.

## 4. Existing API — preserve these endpoints

| Module | Method | Endpoint | Expected success |
| --- | --- | --- | --- |
| Stations | POST | `/stations` | 201 |
| Stations | GET | `/stations` | 200 |
| Stations | GET | `/stations/{station_id}` | 200 |
| Stations | PATCH | `/stations/{station_id}` | 200 |
| Stations | DELETE | `/stations/{station_id}` | 204 |
| Routes | POST | `/routes` | 201 |
| Routes | GET | `/routes` | 200 |
| Routes | GET | `/routes/{route_id}` | 200 |
| Routes | PATCH | `/routes/{route_id}` | 200 |
| Routes | DELETE | `/routes/{route_id}` | 204 |
| Routes | GET | `/routes/{route_id}/exposure` | 200 |
| Routes | GET | `/routes/compare?start=...&end=...` | 200 |
| Saved Routes | POST | `/saved-routes` | 201 |
| Saved Routes | GET | `/saved-routes` | 200 |
| Saved Routes | GET | `/saved-routes/{saved_route_id}` | 200 |
| Saved Routes | PATCH | `/saved-routes/{saved_route_id}` | 200 |
| Saved Routes | DELETE | `/saved-routes/{saved_route_id}` | 204 |

The root health endpoint `GET /` must continue to work. Keep the route-comparison endpoint registered before `/{route_id}` to avoid path collisions.

## 5. Architecture and file ownership

```text
DemAi/
├── main.py
├── database.py               # Shared infrastructure: leader
├── models/
│   ├── __init__.py           # Must import/register all ORM models for Alembic
│   ├── station.py            # Member 1
│   ├── route.py              # Member 2
│   └── saved_route.py        # Member 3
├── schemas/                  # Existing Pydantic schemas; edit only if needed
│   ├── station.py
│   ├── route.py
│   └── saved_route.py
├── routers/                  # Existing FastAPI endpoints
│   ├── stations.py
│   ├── routes.py
│   └── saved_routes.py
├── services/                 # Replace dict access with SQLAlchemy queries
│   ├── station_service.py
│   ├── route_service.py
│   └── saved_route_service.py
├── alembic/
│   ├── env.py
│   └── versions/             # Migration scripts, tracked in Git
├── alembic.ini
├── requirements.txt
├── .env.example              # Safe template, tracked in Git
├── .env                      # Real local secrets, NEVER commit
├── .gitignore
├── tests/
└── README.md
```

The Assignment 5 `store.py` can remain during the transition, but **none of the final database-backed services may depend on its dictionaries**.

### Shared infrastructure contract

The team leader prepares `database.py` containing:

- `engine` — SQLAlchemy engine using `DATABASE_URL` from `.env`
- `SessionLocal` — session factory
- `Base` — shared declarative model base
- `get_db()` — FastAPI dependency yielding and closing a session

Use **one shared engine, one shared Base, and one session dependency**. Do not create new engines/Bases in feature modules. Use SQLAlchemy 2.x `Mapped`, `mapped_column`, `relationship` and `Session`. Avoid circular imports by agreeing on model imports and relationships before merging.

Pass the session from **router → service** with FastAPI's `Depends(get_db)`; keep data rules in the service. For writes, commit and refresh when needed, and roll back on database errors. Convert ORM objects into the expected Pydantic responses (`model_config = ConfigDict(from_attributes=True)` where appropriate), taking care to return computed `air_quality` and `exposure_score` fields.

## 6. Local setup (Windows PowerShell)

Prerequisites: Python, PostgreSQL server running on port 5432, and an existing PostgreSQL database named `demai_db`. The team leader verified PostgreSQL 18 locally; **teammates use their own local databases and credentials**.

```powershell
# From project root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If dependencies are not yet in `requirements.txt`, ensure it includes FastAPI, Uvicorn, Pydantic, SQLAlchemy, Psycopg 3 (`psycopg[binary]` for convenient local setup), Alembic, python-dotenv, and test dependencies.

Create a private `.env` from `.env.example`:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/demai_db
```

**Never commit, screenshot, or share the real `.env` password.** Ensure `.env` and `.venv/` are ignored by Git. URL-encode reserved characters if using a URL-formatted password.

After the complete ORM models and a reviewed initial migration are committed:

```powershell
python -m alembic upgrade head
python -m uvicorn main:app --reload
```

Swagger UI: **http://127.0.0.1:8000/docs**.

To verify a connection locally, use the team's `database.py` engine to execute SQL `SELECT 1` (the leader already performed this successfully on their local machine).

## 7. Alembic workflow — owned by team leader

1. Initialize Alembic and configure `alembic/env.py` to use `Base.metadata` and the environment-configured connection.
2. Make `models/__init__.py` import all three ORM models so their tables appear in `Base.metadata`.
3. Merge all model definitions before generating the **first complete migration**.
4. On an empty intended development database, generate a candidate migration:

   ```powershell
   python -m alembic revision --autogenerate -m "create initial tables"
   ```

5. **Inspect** the generated migration. Confirm tables, foreign keys, constraints, and unique constraints are correct; autogeneration may need manual adjustments.
6. Apply it:

   ```powershell
   python -m alembic upgrade head
   ```

7. Confirm that an empty database can be recreated **using migrations only**. Do not rely on `Base.metadata.create_all()` to create tables on app startup.
8. Commit both configuration and migration scripts. Do not commit database contents.

**Do not generate the initial migration before all ORM models are registered**, otherwise Alembic may generate an incomplete schema. Be careful with autogeneration against the wrong database: review proposed destructive changes before running them.

## 8. Testing and acceptance criteria

Run successful and unsuccessful cases through Swagger UI (`/docs`) and keep/update automated tests where possible.

**Minimum full workflow:**

1. POST Station A (`pm25 = 80`) and Station B (`pm25 = 20`).
2. POST Route 1: Medeu → Center, 15 min, Station A; POST Route 2: Medeu → Center, 25 min, Station B.
3. GET `/routes/compare?start=Medeu&end=Center`: fastest = Route 1; cleanest = Route 2 (scores 1200 vs 500).
4. POST SavedRoute for Route 2 (`preference = cleanest`); repeat for the same user and route → 409.
5. PATCH Station B `pm25` to 100; GET Route 2 exposure and SavedRoute → updated score `2500`. Comparison now favors Route 1 for cleanest if its duration is still 15 min.
6. Attempt to DELETE Station A while a route uses it → 409; DELETE Route 2 while saved → 409.
7. Attempt invalid POST/PATCH (negative distance, identical locations, explicit `null`, unknown related ID, empty PATCH) → appropriate 422/404.
8. Stop and restart the FastAPI process: all created records must still be present.
9. Delete records in dependency order: SavedRoute → Route → Station; 204 on successful DELETE.
10. Confirm a fresh database can be built using `alembic upgrade head`.

**Note:** Real IDs are generated by the database; do not assume IDs will always be `1` and `2` unless the database is empty.

## 9. Collaboration and delivery

- **Member 1:** Stations — `feature/assignment6-stations`
- **Member 2 (leader):** Routes — `feature/assignment6-routes`
- **Member 3:** Saved Routes — `feature/assignment6-saved-routes`
- **Leader foundation:** `feature/assignment6-foundation`; merge this into `main` **before** other members branch from `main`.
- Only the leader edits shared `database.py`, Alembic configuration and initial migration. Coordinate any required changes to `models/__init__.py` and relationship names.
- Make small, focused commits; open PRs into `main`; review before merging.
- Check Git status and confirm **no `.env` or secrets** are included.
- Each PR must explain changed files, commands used, Swagger tests completed, and any remaining limitations.
- Final submission: one team repository link on Moodle before the deadline.

See **`TEAM_TASKS.md`** for individual instructions and copy-paste AI-assistant prompts.

## 10. Context for AI assistants working on this repository

> You are assisting a member of a three-person university team upgrading an existing project named **DemAI** from FastAPI + in-memory dictionaries to FastAPI + PostgreSQL + SQLAlchemy 2.x + Alembic. This is **Assignment 6**, not a greenfield project. Inspect the existing branch's `main.py`, `routers/`, `schemas/`, and `services/` before changing code. Keep the current endpoint paths, success codes, request validation, response shapes, air-quality classification, exposure calculation, route comparison tie-breakers, and restrictive deletion behavior. Use the shared `database.py` (`engine`, `SessionLocal`, `Base`, `get_db`); no new independent engine or Base. Do not invent a Users table or live maps API. Only modify files assigned to your member unless coordinated with the leader. Do not put passwords in source code or Git. Explain changes, test both success and failure cases, and submit work in a feature branch with a pull request. If the foundation or another model needed by your task is absent on the branch, report the dependency instead of silently redesigning the architecture.
