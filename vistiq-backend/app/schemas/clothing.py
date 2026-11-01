"""Pydantic schemas for the wardrobe CRUD API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClothingItemBase(BaseModel):
    """Fields shared by create and response schemas."""

    name: str
    category: str
    color: str
    style: str

    subcategory: str | None = None
    secondary_color: str | None = None
    occasion: str | None = None
    season: str | None = None
    gender: str | None = None
    image: str | None = None
    description: str | None = None
    is_favorite: bool = False
    # Phase 3 — "high" | "medium" | "low" | None (unknown). Set from a
    # Phase 2 photo analysis at creation time; never fabricated for an item
    # that wasn't analyzed. See app/database/models.py's ClothingItem.
    color_reliability: str | None = None


class ClothingItemCreate(ClothingItemBase):
    """Body for POST /wardrobe. wear_count/created_at are set by the server."""


class ClothingItemUpdate(BaseModel):
    """Body for PUT /wardrobe/{id}. Every field is optional — only the
    fields the client actually sends are changed. id and created_at are
    intentionally not included here, so a client can never overwrite them.
    """

    name: str | None = None
    category: str | None = None
    color: str | None = None
    style: str | None = None
    subcategory: str | None = None
    secondary_color: str | None = None
    occasion: str | None = None
    season: str | None = None
    gender: str | None = None
    image: str | None = None
    description: str | None = None
    wear_count: int | None = None
    is_favorite: bool | None = None
    color_reliability: str | None = None


class ClothingItemResponse(ClothingItemBase):
    """What the API returns for a clothing item."""

    id: int
    wear_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImageUploadResponse(BaseModel):
    """Body for POST /wardrobe/images. `image` is a relative, servable URL
    (e.g. "/uploads/<uuid>.jpg") — pass it straight through as the `image`
    field on a subsequent POST /wardrobe call."""

    image: str
