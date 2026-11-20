
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.station import Station
    from models.saved_route import SavedRoute


class Route(Base):
    __tablename__ = "routes"

    __table_args__ = (
        CheckConstraint(
            "distance_km > 0",
            name="ck_routes_distance_positive"
        ),
        CheckConstraint(
            "duration_min > 0",
            name="ck_routes_duration_positive"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    start: Mapped[str] = mapped_column(String(100), nullable=False)
    end: Mapped[str] = mapped_column(String(100), nullable=False)

    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)

    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="RESTRICT"),nullable=False)

    station: Mapped["Station"] = relationship(back_populates="routes")

    saved_routes: Mapped[list["SavedRoute"]] = relationship(back_populates="route")
