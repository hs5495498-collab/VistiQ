"""SQLAlchemy ORM models for the VISTIQ database."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class User(Base):
    """A registered VISTIQ account (Phase 4).

    `password_hash` is an Argon2id hash (app/security/passwords.py) — the
    plaintext password is never stored, never logged, and this column is
    never included in any API response schema (see
    app/schemas/auth.py:UserPublic, which deliberately omits it).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Stored normalized (lowercased + stripped) — see
    # app/security/passwords.py's normalize_email() — so "A@B.com" and
    # "a@b.com" are correctly treated as the same account.
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class UserSession(Base):
    """A single logged-in session (Phase 4).

    Opaque, cryptographically random token (app/security/sessions.py) —
    only `token_hash` (its SHA-256 digest) is ever stored here. The raw
    token itself lives only in the user's HttpOnly cookie; a leaked
    database can never be used to reconstruct a valid session token. A new
    row (never a reused one) is created on every successful login —
    session rotation, the standard defense against session fixation.
    """

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship("User")


class ClothingItem(Base):
    """A single wardrobe garment."""

    __tablename__ = "clothing_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Phase 4: nullable so existing pre-Phase-4 rows (created before user
    # accounts existed) don't need a value assigned to keep working at the
    # database level. In practice they become permanently unreachable
    # through the now user-scoped API (NULL never equals any real user's
    # id) — preserved on disk, never deleted, never exposed to a new
    # account. See app/routes/wardrobe.py's ownership filtering.
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)

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
