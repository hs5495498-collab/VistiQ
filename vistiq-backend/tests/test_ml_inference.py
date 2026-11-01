"""Unit tests for ml/inference/predict.py and color.py. The trained
PyTorch model itself is mocked here (a real forward pass is expensive and
already covered, unmocked, by tests/test_model_smoke.py) — these tests
verify predict_clothing()'s contract: six-category output structure, valid
confidence values, and correct low-confidence flagging."""

import torch
from PIL import Image

from ml.inference import predict
from ml.inference.color import extract_dominant_color
from ml.training.config import LOW_CONFIDENCE_THRESHOLD, VISTIQ_CATEGORIES


class _FakeModel:
    """Stands in for the real MobileNetV3 model — returns fixed logits
    instead of running a real (expensive) forward pass."""

    def __init__(self, logits: list[float]):
        self._logits = torch.tensor([logits])

    def __call__(self, _input_tensor):
        return self._logits


def _solid_image(color=(10, 10, 10)) -> Image.Image:
    return Image.new("RGB", (32, 32), color=color)


def test_predict_clothing_returns_six_category_structure(monkeypatch):
    # Strongly favors index 0 ("Tops") so the result is deterministic.
    logits = [10.0] + [0.0] * (len(VISTIQ_CATEGORIES) - 1)
    monkeypatch.setattr(predict, "_get_model", lambda model_path=None: _FakeModel(logits))
    monkeypatch.setattr(predict, "_model", None)

    result = predict.predict_clothing(_solid_image())

    assert set(result.keys()) == {"category", "confidence", "low_confidence", "color", "color_confidence"}
    assert result["category"] in VISTIQ_CATEGORIES
    assert result["category"] == VISTIQ_CATEGORIES[0]


def test_predict_clothing_confidence_is_valid_probability(monkeypatch):
    logits = [10.0] + [0.0] * (len(VISTIQ_CATEGORIES) - 1)
    monkeypatch.setattr(predict, "_get_model", lambda model_path=None: _FakeModel(logits))
    monkeypatch.setattr(predict, "_model", None)

    result = predict.predict_clothing(_solid_image())

    assert 0.0 <= result["confidence"] <= 1.0


def test_predict_clothing_color_confidence_always_none(monkeypatch):
    logits = [10.0] + [0.0] * (len(VISTIQ_CATEGORIES) - 1)
    monkeypatch.setattr(predict, "_get_model", lambda model_path=None: _FakeModel(logits))
    monkeypatch.setattr(predict, "_model", None)

    result = predict.predict_clothing(_solid_image())

    assert result["color_confidence"] is None


def test_predict_clothing_flags_low_confidence_below_threshold(monkeypatch):
    # Near-uniform logits -> near-uniform softmax -> top class confidence
    # well below LOW_CONFIDENCE_THRESHOLD.
    logits = [0.01] * len(VISTIQ_CATEGORIES)
    monkeypatch.setattr(predict, "_get_model", lambda model_path=None: _FakeModel(logits))
    monkeypatch.setattr(predict, "_model", None)

    result = predict.predict_clothing(_solid_image())

    assert result["confidence"] < LOW_CONFIDENCE_THRESHOLD
    assert result["low_confidence"] is True


def test_predict_clothing_does_not_flag_high_confidence(monkeypatch):
    logits = [10.0] + [0.0] * (len(VISTIQ_CATEGORIES) - 1)
    monkeypatch.setattr(predict, "_get_model", lambda model_path=None: _FakeModel(logits))
    monkeypatch.setattr(predict, "_model", None)

    result = predict.predict_clothing(_solid_image())

    assert result["confidence"] >= LOW_CONFIDENCE_THRESHOLD
    assert result["low_confidence"] is False


# --- Color extraction (real, deterministic, cheap — not mocked) -------------


def test_extract_dominant_color_returns_known_bucket():
    color_name, rgb = extract_dominant_color(_solid_image(color=(20, 20, 20)))
    assert color_name == "Black"
    assert isinstance(rgb, tuple) and len(rgb) == 3


def test_extract_dominant_color_handles_all_white_image_without_crashing():
    # Entirely background-colored image -> the foreground-pixel filter would
    # otherwise leave zero samples; color.py falls back to the full pixel
    # set rather than crashing on an empty selection.
    color_name, _rgb = extract_dominant_color(_solid_image(color=(255, 255, 255)))
    assert color_name == "White"


def test_is_model_available_false_for_missing_path(tmp_path):
    missing = tmp_path / "does_not_exist.pt"
    assert predict.is_model_available(missing) is False
