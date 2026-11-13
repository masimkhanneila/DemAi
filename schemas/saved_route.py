from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, field_validator


RoutePreference = Literal["fastest", "cleanest"]
RouteLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SavedRouteCreate(BaseModel):
    user_id: int
    route_id: int
    label: RouteLabel
    preference: RoutePreference


class SavedRouteUpdate(BaseModel):
    user_id: int | None = None
    route_id: int | None = None
    label: RouteLabel | None = None
    preference: RoutePreference | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null. Omit it to keep its current value.")
        return value


class SavedRouteResponse(SavedRouteCreate):
    id: int
    exposure_score: float