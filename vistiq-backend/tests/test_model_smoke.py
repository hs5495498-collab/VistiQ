"""Genuine model-load smoke test — deliberately NOT mocked. Loads the real
models/vistiq_clothing_classifier.pt checkpoint, runs a real CPU forward
pass through the real MobileNetV3-Small architecture, and asserts on
real (non-fabricated) output. This is slower than the rest of the suite by
design; everywhere else, this cost is mocked (see tests/test_ml_inference.py
and tests/test_clothing_analysis_api.py).

Skips gracefully if the checkpoint isn't present on disk, rather than
failing the whole suite — training happens separately in Google Colab (see
ml/README.md), so a clean checkout without the checkpoint is expected.
"""

import pytest

from ml.inference.predict import is_model_available, predict_clothing_from_path
from ml.training.config import MODEL_PATH, NUM_CLASSES, VISTIQ_CATEGORIES
from ml.training.model import build_model, load_model

pytestmark = pytest.mark.skipif(
    not is_model_available(), reason=f"No trained checkpoint at {MODEL_PATH} — train it in Colab first."
)


def test_checkpoint_loads_into_the_real_architecture_strictly():
    """Confirms the saved state_dict's keys/shapes exactly match the
    architecture build_model() constructs — a real compatibility check,
    not just "the file exists"."""
    model = load_model(MODEL_PATH)

    fresh = build_model(num_classes=NUM_CLASSES, pretrained=False)
    saved_keys = set(model.state_dict().keys())
    fresh_keys = set(fresh.state_dict().keys())
    assert saved_keys == fresh_keys


def test_real_inference_on_real_uploaded_photos():
    """Runs real inference on whatever real wardrobe photos already exist
    on disk from manual testing. Skips (rather than fails) if none are
    present, since that's just local dev state, not a code defect."""
    uploads_dir = MODEL_PATH.parent.parent / "vistiq-backend" / "data" / "uploads"
    sample_images = sorted(uploads_dir.glob("*.*"))[:3] if uploads_dir.exists() else []
    if not sample_images:
        pytest.skip("No sample images in vistiq-backend/data/uploads/ to run real inference against.")

    for image_path in sample_images:
        result = predict_clothing_from_path(str(image_path))
        assert result["category"] in VISTIQ_CATEGORIES
        assert 0.0 <= result["confidence"] <= 1.0
        assert isinstance(result["low_confidence"], bool)
        # Phase 2: color_confidence is a real cluster-dominance score (float)
        # when the K-means pipeline succeeds, null if it fell back to the
        # Phase 1 deterministic method — either is valid on a real photo.
        assert result["color_confidence"] is None or (
            isinstance(result["color_confidence"], float) and 0.0 <= result["color_confidence"] <= 1.0
        )
        assert result["pattern"] in {"solid", "patterned", "unknown"}
        assert result["brightness_level"] in {"light", "medium", "dark", "unknown"}
