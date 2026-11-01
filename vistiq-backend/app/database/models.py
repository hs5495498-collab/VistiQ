"""SQLAlchemy ORM models for the VISTIQ database."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class ClothingItem(Base):
    """A single wardrobe garment."""

    __tablename__ = "clothing_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String, nullable=True)
    color: Mapped[str] = mapped_column(String, nullable=False)
    secondary_color: Mapped[str | None] = mapped_column(String, nullable=True)
    # Phase 3: populated when a new item is saved from a Phase 2 photo
    # analysis ("high"/"medium"/"low"). NULL for items created before this
    # column existed, or created without a photo analysis — the
    # recommendation engine treats NULL as "unknown" and does NOT penalize
    # it, exactly like a known-high-reliability item (see
    # app/recommendation/color_theory.py).
    color_reliability: Mapped[str | None] = mapped_column(String, nullable=True)
    style: Mapped[str] = mapped_column(String, nullable=False)
    occasion: Mapped[str | None] = mapped_column(String, nullable=True)
    season: Mapped[str | None] = mapped_column(String, nullable=True)
    gender: Mapped[str | None] = mapped_column(String, nullable=True)
    image: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    wear_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_favorite: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
