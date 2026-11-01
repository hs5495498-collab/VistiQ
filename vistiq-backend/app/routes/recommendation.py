"""FastAPI endpoint for the recommendation engine. All logic lives in
app/recommendation/ — this file only wires the HTTP layer to it.

Phase 4: requires authentication and passes the authenticated user's id
through to build_recommendations(), which scopes every wardrobe query to
it — a user can only ever generate recommendations from (or anchor on)
their own wardrobe items."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.recommendation.engine import build_recommendations
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.security.dependencies import get_current_user, require_csrf

router = APIRouter(prefix="/recommend", tags=["recommendation"])


@router.post(
    "",
    response_model=RecommendationResponse,
    summary="Generate ranked outfit recommendations from the authenticated user's wardrobe pool",
    dependencies=[Depends(require_csrf)],
)
def recommend(
    request: RecommendationRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return build_recommendations(db, request, current_user.id)
