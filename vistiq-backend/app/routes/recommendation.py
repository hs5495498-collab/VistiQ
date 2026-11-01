"""FastAPI endpoint for the recommendation engine. All logic lives in
app/recommendation/ — this file only wires the HTTP layer to it."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.recommendation.engine import build_recommendations
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse

router = APIRouter(prefix="/recommend", tags=["recommendation"])


@router.post(
    "",
    response_model=RecommendationResponse,
    summary="Generate ranked outfit recommendations from a wardrobe pool",
)
def recommend(request: RecommendationRequest, db: Session = Depends(get_db)):
    return build_recommendations(db, request)
