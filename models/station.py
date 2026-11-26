from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.route import Route


class Station(Base):
    __tablename__ = "stations"
    __table_args__ = (
        CheckConstraint("pm25 >= 0", name="ck_stations_pm25_non_negative"),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_stations_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_stations_longitude_range",
        ),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name="ck_stations_coordinates_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(100), nullable=False)
    pm25: Mapped[float] = mapped_column(Float, nullable=False)

    # Optional: stations created before Assignment 7 have no coordinates.
    # PM2.5 can be refreshed from Open-Meteo only when both values are set.
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    
    routes: Mapped[list["Route"]] = relationship(
        back_populates="station",
        passive_deletes="all",
    )