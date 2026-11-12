from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class AirQuality(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class StationCreate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    name: NonEmptyStr = Field(examples=["Medeu"])
    location: NonEmptyStr = Field(examples=["Almaty, Medeu district"])
    pm25: float = Field(ge=0, examples=[60.0], description="PM2.5, µg/m³ (>= 0)")


class StationUpdate(BaseModel):
    

    model_config = ConfigDict(extra="forbid")

    name: Optional[NonEmptyStr] = None
    location: Optional[NonEmptyStr] = None
    pm25: Optional[float] = Field(default=None, ge=0)

    
    @field_validator("name", "location", "pm25", mode="before")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("field cannot be null")
        return value


class StationResponse(BaseModel):

    id: int
    name: str
    location: str
    pm25: float
    air_quality: AirQuality
