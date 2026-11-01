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

from ml.inference.predict import ModelUnavailableError, is_model_available, predict_clothing  # noqa: E402
from ml.training.config import LOW_CONFIDENCE_THRESHOLD  # noqa: E402

__all__ = ["analyze_clothing_image", "ModelUnavailableError", "is_model_available"]


def analyze_clothing_image(image) -> dict:
    """image: an already-opened PIL.Image.Image (the route handles reading
    the upload and opening it). Raises ModelUnavailableError if no trained
    model file exists yet — the route is responsible for turning that into
    a 503 response instead of a crash."""
    result = predict_clothing(image)
    result["message"] = (
        "Clothing image analyzed successfully"
        if not result["low_confidence"]
        else f"Low-confidence prediction (below {LOW_CONFIDENCE_THRESHOLD:.0%}) — please review before saving."
    )
    return result
