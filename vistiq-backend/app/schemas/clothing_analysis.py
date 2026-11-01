"""Pydantic response schema for POST /analyze-clothing."""

from pydantic import BaseModel


class ClothingAnalysisResponse(BaseModel):
    category: str
    confidence: float
    low_confidence: bool
    color: str
    # Always null — color comes from deterministic image processing
    # (ml/inference/color.py), not the trained model, so it has no ML
    # confidence score. See ml/README.md "Color extraction (not ML)".
    color_confidence: float | None
    message: str
