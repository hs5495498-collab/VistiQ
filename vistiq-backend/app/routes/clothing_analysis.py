"""POST /analyze-clothing — ML clothing image analysis (Stage 13).

Kept deliberately separate from wardrobe creation: this endpoint only
analyzes an uploaded photo and returns a prediction for the user to review.
It does NOT create a wardrobe record — that still only happens via the
existing POST /wardrobe, with whatever the user confirms after reviewing
this prediction.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas.clothing_analysis import ClothingAnalysisResponse
from app.services.clothing_analysis import ImageQualityError, ModelUnavailableError, analyze_clothing_image
from app.services.image_validation import read_and_validate_image

router = APIRouter(tags=["clothing-analysis"])


@router.post(
    "/analyze-clothing",
    response_model=ClothingAnalysisResponse,
    summary="Predict clothing category and dominant color from an uploaded photo",
)
async def analyze_clothing(file: UploadFile = File(...)):
    _raw_bytes, image = await read_and_validate_image(file)

    try:
        return analyze_clothing_image(image)
    except ImageQualityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ModelUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Clothing analysis model is not available.",
        )
