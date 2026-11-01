"""
Inference entry point: predict_clothing(image) -> structured prediction.

Used both standalone (CLI / notebook "single-image prediction" section) and
by the FastAPI backend (app/services/clothing_analysis.py imports this
module directly — see that file for how the sibling `ml/` package is put on
sys.path).

Category + confidence come from the trained MobileNetV3 classifier (real ML).
Color comes from ml/inference/color.py (deterministic image processing, not
ML) — this distinction is preserved all the way to the API response, which
is why color_confidence is always null.
"""

from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms

from ml.inference.color import extract_dominant_color
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

    color_name, _dominant_rgb = extract_dominant_color(rgb_image)

    return {
        "category": category,
        "confidence": round(confidence, 4),
        "low_confidence": confidence < LOW_CONFIDENCE_THRESHOLD,
        "color": color_name,
        "color_confidence": None,  # deterministic image processing, not ML — see color.py
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
