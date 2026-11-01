"""API-level tests for POST /analyze-clothing. The actual PyTorch model
load/inference is mocked here (via app.services.clothing_analysis) — it is
expensive and already covered by the real end-to-end check in
tests/test_model_smoke.py."""

import io

from PIL import Image

from app.services import clothing_analysis


def _valid_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=(200, 50, 50)).save(buf, format="JPEG")
    return buf.getvalue()


def test_analyze_clothing_success(client, monkeypatch):
    def fake_predict_clothing(image):
        return {
            "category": "Tops",
            "confidence": 0.97,
            "low_confidence": False,
            "color": "Red",
            "color_confidence": None,
        }

    monkeypatch.setattr(clothing_analysis, "predict_clothing", fake_predict_clothing)

    files = {"file": ("shirt.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    response = client.post("/analyze-clothing", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "Tops"
    assert body["confidence"] == 0.97
    assert body["low_confidence"] is False
    assert body["color"] == "Red"
    assert body["color_confidence"] is None


def test_analyze_clothing_low_confidence_message(client, monkeypatch):
    def fake_predict_clothing(image):
        return {
            "category": "Outerwear",
            "confidence": 0.42,
            "low_confidence": True,
            "color": "Grey",
            "color_confidence": None,
        }

    monkeypatch.setattr(clothing_analysis, "predict_clothing", fake_predict_clothing)

    files = {"file": ("item.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    response = client.post("/analyze-clothing", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["low_confidence"] is True
    assert "review" in body["message"].lower()


def test_analyze_clothing_model_unavailable_returns_503(client, monkeypatch):
    def fake_predict_clothing(image):
        raise clothing_analysis.ModelUnavailableError("no checkpoint")

    monkeypatch.setattr(clothing_analysis, "predict_clothing", fake_predict_clothing)

    files = {"file": ("item.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    response = client.post("/analyze-clothing", files=files)

    assert response.status_code == 503


def test_analyze_clothing_invalid_image_rejected_before_model_call(client, monkeypatch):
    """Invalid-image rejection happens in image_validation.py, before the
    (mocked-out) model is ever consulted — assert the mock is never called."""
    calls = []

    def fake_predict_clothing(image):
        calls.append(image)
        return {}

    monkeypatch.setattr(clothing_analysis, "predict_clothing", fake_predict_clothing)

    files = {"file": ("not-an-image.jpg", b"definitely not an image", "image/jpeg")}
    response = client.post("/analyze-clothing", files=files)

    assert response.status_code == 400
    assert calls == []
