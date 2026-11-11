# DemAi
DemAI – Eco-Friendly Route Recommendation REST API built with FastAPI

## Data Models

### 1. Station (Person 1 — Air Quality Monitoring)

| Field | Type | Description |
|---|---|---|
| id | int | Unique station ID |
| name | str | Station name |
| location | str | Station location |
| pm25 | float | PM2.5 pollution level |

### 2. Route (Person 2 — Route Comparison)

| Field | Type | Description |
|---|---|---|
| id | int | Unique route ID |
| start | str | Starting location |
| end | str | Destination |
| distance_km | float | Route distance in kilometers |
| duration_min | int | Walking duration in minutes |
| station_id | int | Related monitoring station ID |

### 3. SavedRoute (Person 3 — Saved Routes)

| Field | Type | Description |
|---|---|---|
| id | int | Unique saved route ID |
| user_id | int | User identifier |
| route_id | int | Referenced route ID |
| label | str | Custom route name |
| preference | str | fastest or cleanest |

## Business Rules

### Station Management
- Station names cannot be empty.
- PM2.5 values must be greater than or equal to 0.
- Each station must have a unique ID.
- A station cannot be deleted if it is referenced by an existing route.
- Pollution classification is calculated automatically:
  - Low: PM2.5 < 15
  - Moderate: 15 <= PM2.5 < 35
  - High: PM2.5 >= 35

### Route Management
- Every route must reference an existing station.
- Distance and duration must be greater than 0.
- A route's start and end locations cannot be the same.
- Estimated pollution exposure score is calculated as:
  exposure = station.pm25 * route.duration_min
- Fastest route: route with the shortest duration.
- Cleanest route: route with the lowest exposure score.
- Routes can only be compared when they have the same start and end locations.
- A route cannot be deleted if it is referenced by a saved route.

### Saved Route Management
- A saved route must reference an existing route.
- A user cannot save the same route twice.
- Preference must be either "fastest" or "cleanest".
- Saved route labels cannot be empty.
- When retrieving a saved route, its current exposure score must be calculated using the latest station data.
- Users can update or delete their saved routes.

## Error Handling

| HTTP Status | Meaning |
|---|---|
| 200 OK | Successful GET, PATCH or PUT |
| 201 Created | Resource successfully created |
| 204 No Content | Resource successfully deleted |
| 404 Not Found | Requested resource does not exist |
| 409 Conflict | Business rule conflict |
| 422 Unprocessable Entity | Invalid request data |

## Shared Storage

All resources are stored in Python dictionaries inside `store.py`.

- `stations` stores monitoring stations.
- `routes` stores walking routes.
- `saved_routes` stores saved routes.
- All dictionary keys are integer IDs.
- All services must use these shared dictionaries.

Data is stored in memory and resets when the application restarts.
