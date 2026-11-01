"""
Wraps ml/inference/predict.py for FastAPI.

The `ml` package lives outside vistiq-backend/ — it's a sibling directory
under the project root, alongside vistiq-frontend/ and Stitch/ (see
ml/README.md). This module adds the project root to sys.path before
importing it: a small, explicit, documented path hack, rather than
duplicating inference code inside the backend or turning `ml` into a
separately-installed package (unnecessary for this project's scope).
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # services -> app -> vistiq-backend -> VistiQ
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ml.inference.image_quality import ImageQualityError, assess_image_quality  # noqa: E402
from ml.inference.predict import ModelUnavailableError, is_model_available, predict_clothing  # noqa: E402
from ml.training.config import LOW_CONFIDENCE_THRESHOLD  # noqa: E402

__all__ = ["analyze_clothing_image", "ModelUnavailableError", "ImageQualityError", "is_model_available"]


def analyze_clothing_image(image) -> dict:
    """image: an already-opened PIL.Image.Image (the route handles reading
    the upload and opening it).

    Raises ImageQualityError (Phase 2) for the one hard-reject image-quality
    case (too small to analyze) — checked BEFORE running the classifier, so
    an unusable image never wastes a model forward pass. Raises
    ModelUnavailableError if no trained model file exists yet. Both are
    caught by the route and turned into a clean HTTP error instead of a
    crash — see app/routes/clothing_analysis.py.
    """
    quality_report = assess_image_quality(image)

    result = predict_clothing(image)
    result["quality_warnings"] = quality_report.warnings

    message = (
        "Clothing image analyzed successfully"
        if not result["low_confidence"]
        else f"Low-confidence prediction (below {LOW_CONFIDENCE_THRESHOLD:.0%}) — please review before saving."
    )
    if quality_report.warnings:
        message += " " + " ".join(quality_report.warnings)
    result["message"] = message

    return result
