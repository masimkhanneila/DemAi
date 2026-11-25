from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.route import Route


class SavedRoute(Base):
    __tablename__ = "saved_routes"
    __table_args__ = (
        UniqueConstraint("user_id", "route_id", name="uq_saved_routes_user_route"),
        CheckConstraint("length(trim(label)) > 0", name="ck_saved_routes_label_nonblank"),
        CheckConstraint(
            "preference IN ('fastest', 'cleanest')",
            name="ck_saved_routes_preference",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
        user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            name="fk_saved_routes_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="RESTRICT"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    preference: Mapped[str] = mapped_column(String(20), nullable=False)

    route: Mapped["Route"] = relationship(back_populates="saved_routes")
