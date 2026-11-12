from pydantic import BaseModel, Field, field_validator, model_validator


class RouteCreate(BaseModel):
    start: str = Field(min_length=1)
    end: str = Field(min_length=1)
    distance_km: float = Field(gt=0, allow_inf_nan=False)
    duration_min: int = Field(gt=0)
    station_id: int = Field(gt=0)

    @field_validator("start", "end")
    @classmethod
    def clean_location(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Location cannot be empty")
        return value

    @model_validator(mode="after")
    def different_locations(self):
        if self.start.casefold() == self.end.casefold():
            raise ValueError("Start and end cannot be the same")
        return self


class RouteUpdate(BaseModel):
    start: str | None = None
    end: str | None = None
    distance_km: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    duration_min: int | None = Field(default=None, gt=0)
    station_id: int | None = Field(default=None, gt=0)

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError("Field cannot be null; omit it instead")
        return value

    @field_validator("start", "end")
    @classmethod
    def clean_location(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("Location cannot be empty")
        return value

    @model_validator(mode="after")
    def different_locations_if_both_supplied(self):
        if self.start is not None and self.end is not None:
            if self.start.casefold() == self.end.casefold():
                raise ValueError("Start and end cannot be the same")
        return self


class RouteResponse(RouteCreate):
    id: int = Field(gt=0)


class RouteWithExposure(RouteResponse):
    pm25: float = Field(ge=0)
    exposure_score: float = Field(ge=0)


class RouteComparison(BaseModel):
    start: str
    end: str
    total_routes: int
    fastest: RouteWithExposure
    cleanest: RouteWithExposure
