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
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(100), nullable=False)
    pm25: Mapped[float] = mapped_column(Float, nullable=False)

    
    routes: Mapped[list["Route"]] = relationship(
        back_populates="station",
        passive_deletes="all",
    )
