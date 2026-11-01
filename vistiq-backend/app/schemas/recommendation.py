"""Pydantic request/response schemas for POST /recommend."""

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    occasion: str
    style: str | None = None
    weather: str | None = None
    wardrobe_item_ids: list[int] = Field(default_factory=list)
    selected_item_id: int | None = None
    top_k: int = Field(default=3, ge=1, le=10)

    # --- Phase 3: optional, request-scoped personalization (no accounts,
    # no persisted preferences — see app/recommendation/personalization.py).
    # Every field defaults to "no preference", so an existing client that
    # sends none of these keeps working exactly as before. ---
    preferred_colors: list[str] = Field(default_factory=list)
    avoided_colors: list[str] = Field(default_factory=list)
    prefer_favorites: bool = False

    # Phase 3: diversity-aware reranking (see
    # app/recommendation/diversity.py) is applied by default; exposed as an
    # opt-out, not an opt-in, so existing behavior-adjacent callers that
    # don't know about it still get the (now default) improved behavior.
    diversify: bool = True


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

    # --- Phase 3: structured explainability — additive, `reason` (above)
    # is unchanged in name/type/meaning. See
    # app/recommendation/engine.py's _build_explanation(). ---
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    positive_reasons: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class RecommendationContext(BaseModel):
    occasion: str
    style: str | None
    weather: str | None
    selected_item_id: int | None


class RecommendationResponse(BaseModel):
    request: RecommendationContext
    recommendations: list[OutfitRecommendation]
    message: str | None = None
