from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Latitude = Annotated[float, Field(ge=-90, le=90, description="WGS84 latitude, degrees")]
Longitude = Annotated[float, Field(ge=-180, le=180, description="WGS84 longitude, degrees")]


class AirQuality(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


def _require_coordinate_pair(latitude_given: bool, longitude_given: bool) -> None:
    if latitude_given != longitude_given:
        raise ValueError("latitude and longitude must be provided together")


class StationCreate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    name: NonEmptyStr = Field(examples=["Medeu"])
    location: NonEmptyStr = Field(examples=["Almaty, Medeu district"])
    pm25: float = Field(ge=0, examples=[60.0], description="PM2.5, µg/m³ (>= 0)")
    latitude: Optional[Latitude] = Field(default=None, examples=[43.1575])
    longitude: Optional[Longitude] = Field(default=None, examples=[77.0589])

    @model_validator(mode="after")
    def coordinates_together(self):
        _require_coordinate_pair(self.latitude is not None, self.longitude is not None)
        return self


class StationUpdate(BaseModel):
    

    model_config = ConfigDict(extra="forbid")

    name: Optional[NonEmptyStr] = None
    location: Optional[NonEmptyStr] = None
    pm25: Optional[float] = Field(default=None, ge=0)
    latitude: Optional[Latitude] = None
    longitude: Optional[Longitude] = None

    
    @field_validator("name", "location", "pm25", "latitude", "longitude", mode="before")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("field cannot be null")
        return value

    @model_validator(mode="after")
    def coordinates_together(self):
        _require_coordinate_pair(
            "latitude" in self.model_fields_set,
            "longitude" in self.model_fields_set,
        )
        return self


class StationResponse(BaseModel):

    id: int
    name: str
    location: str
    pm25: float
    air_quality: AirQuality
    latitude: Optional[float] = None
    longitude: Optional[float] = None