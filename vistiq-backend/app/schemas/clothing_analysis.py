"""Pydantic response schema for POST /analyze-clothing.

Phase 2 fields below are purely additive (new, defaulted, optional) —
every field that existed before Phase 2 keeps its exact name and type, so
any client reading only the original fields is unaffected.
"""

from pydantic import BaseModel, Field


class ClothingAnalysisResponse(BaseModel):
    category: str
    confidence: float
    low_confidence: bool
    color: str
    # Non-null when Phase 2's K-means color pipeline succeeds (a real
    # cluster-dominance score, 0-1 — NOT a machine-learning confidence
    # value); null when it falls back to the Phase 1 deterministic method,
    # exactly as it always was before Phase 2. See
    # ml/inference/color_advanced.py's module docstring.
    color_confidence: float | None
    message: str

    # --- Phase 2 additions (all optional/defaulted — additive only) ---
    secondary_color: str | None = None
    color_hex: str | None = None
    color_reliability: str | None = None  # "high" | "medium" | "low"
    segmentation_applied: bool = False
    pattern: str | None = None  # "solid" | "patterned" | "unknown"
    brightness_level: str | None = None  # "light" | "medium" | "dark" | "unknown"
    quality_warnings: list[str] = Field(default_factory=list)
