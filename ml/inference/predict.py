"""
Inference entry point: predict_clothing(image) -> structured prediction.

Used both standalone (CLI / notebook "single-image prediction" section) and
by the FastAPI backend (app/services/clothing_analysis.py imports this
module directly — see that file for how the sibling `ml/` package is put on
sys.path).

Category + confidence come from the trained MobileNetV3 classifier (real
ML — the only learned model anywhere in this pipeline). Color, pattern, and
brightness come from ml/inference/color_advanced.py (Phase 2: GrabCut
segmentation + K-means clustering — classical image processing, NOT a
trained/learned model), which itself falls back to the original Phase 1
ml/inference/color.py deterministic method whenever the advanced pipeline
can't produce a trustworthy result. `color_confidence` reflects that: it's
populated with a real (non-ML) cluster-dominance score when the advanced
pipeline succeeds, and null when it falls back to the Phase 1 method —
never a machine-learning confidence value either way.
"""

from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms

from ml.inference import segmentation
from ml.inference.color_advanced import extract_color_profile
from ml.training.config import (
    IMAGE_SIZE,
    IMAGENET_MEAN,
    IMAGENET_STD,
    LOW_CONFIDENCE_THRESHOLD,
    MODEL_PATH,
    VISTIQ_CATEGORIES,
)
from ml.training.model import load_model

_TRANSFORM = transforms.Compose(
    [
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ]
)

_model = None  # lazily loaded singleton — loaded once per process


class ModelUnavailableError(RuntimeError):
    """Raised when the trained model file doesn't exist yet. Callers (the
    FastAPI route) must catch this and return a clear service error instead
    of crashing or fabricating a prediction."""


def is_model_available(model_path: Path = MODEL_PATH) -> bool:
    return model_path.exists()


def _get_model(model_path: Path = MODEL_PATH):
    global _model
    if _model is None:
        if not model_path.exists():
            raise ModelUnavailableError(
                f"Trained model not found at {model_path}. Train it in the "
                f"Colab notebook (ml/notebooks/vistiq_clothing_classifier_colab.ipynb) "
                f"and place the exported .pt file at that path."
            )
        _model = load_model(model_path)
    return _model


def predict_clothing(image: Image.Image, model_path: Path = MODEL_PATH) -> dict:
    """Run the trained classifier + deterministic color extraction on a
    single already-opened PIL image. Raises ModelUnavailableError if no
    trained model file is present — callers must handle that explicitly."""
    model = _get_model(model_path)

    rgb_image = image.convert("RGB")
    input_tensor = _TRANSFORM(rgb_image).unsqueeze(0)

    with torch.no_grad():
        logits = model(input_tensor)
        probabilities = torch.softmax(logits, dim=1)[0]

    top_index = int(torch.argmax(probabilities))
    category = VISTIQ_CATEGORIES[top_index]
    confidence = float(probabilities[top_index])

    segmentation_result = segmentation.segment_foreground(rgb_image)
    color_profile = extract_color_profile(rgb_image, segmentation_result)

    return {
        "category": category,
        "confidence": round(confidence, 4),
        "low_confidence": confidence < LOW_CONFIDENCE_THRESHOLD,
        "color": color_profile.primary.name,
        # Real (non-ML) cluster-dominance score when the Phase 2 K-means
        # pipeline succeeds; null when it fell back to the Phase 1
        # deterministic method — see this module's docstring.
        "color_confidence": (
            color_profile.primary.percentage if color_profile.method == "kmeans" else None
        ),
        # --- Additive Phase 2 fields — see ml/inference/color_advanced.py ---
        "color_hex": color_profile.primary.hex,
        "secondary_color": color_profile.secondary.name if color_profile.secondary else None,
        "color_reliability": color_profile.reliability,
        "segmentation_applied": color_profile.segmentation_applied,
        "pattern": color_profile.pattern,
        "brightness_level": color_profile.brightness_level,
    }


def predict_clothing_from_path(image_path: str, model_path: Path = MODEL_PATH) -> dict:
    """Convenience wrapper for CLI/notebook use against a file on disk."""
    with Image.open(image_path) as image:
        return predict_clothing(image, model_path=model_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m ml.inference.predict <path-to-image>")

    result = predict_clothing_from_path(sys.argv[1])
    print(result)
