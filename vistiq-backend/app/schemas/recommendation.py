"""Pydantic request/response schemas for POST /recommend."""

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    occasion: str
    style: str | None = None
    weather: str | None = None
    wardrobe_item_ids: list[int] = Field(default_factory=list)
    selected_item_id: int | None = None
    top_k: int = Field(default=3, ge=1, le=10)


class RecommendedClothingItem(BaseModel):
    id: int
    name: str
    category: str
    color: str
    style: str


class OutfitRecommendation(BaseModel):
    rank: int
    score: float
    items: list[RecommendedClothingItem]
    reason: str


class RecommendationContext(BaseModel):
    occasion: str
    style: str | None
    weather: str | None
    selected_item_id: int | None


class RecommendationResponse(BaseModel):
    request: RecommendationContext
    recommendations: list[OutfitRecommendation]
    message: str | None = None
