"""API-level tests for POST /analyze-clothing. The actual PyTorch model
load/inference is mocked here (via app.services.clothing_analysis) — it is
expensive and already covered by the real end-to-end check in
tests/test_model_smoke.py."""

import io

from PIL import Image

from app.services import clothing_analysis


def _valid_jpeg_bytes(size: tuple[int, int] = (64, 64)) -> bytes:
    # 64x64 comfortably clears Phase 2's MIN_HARD_DIMENSION=32 quality
    # floor (ml/inference/image_quality.py) while staying small/fast for
    # tests that don't care about quality thresholds themselves.
    buf = io.BytesIO()
    Image.new("RGB", size, color=(200, 50, 50)).save(buf, format="JPEG")
    return buf.getvalue()


def test_analyze_clothing_success(authenticated_client, monkeypatch):
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
    response = authenticated_client.post("/analyze-clothing", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "Tops"
    assert body["confidence"] == 0.97
    assert body["low_confidence"] is False
    assert body["color"] == "Red"
    assert body["color_confidence"] is None


def test_analyze_clothing_low_confidence_message(authenticated_client, monkeypatch):
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
    response = authenticated_client.post("/analyze-clothing", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["low_confidence"] is True
    assert "review" in body["message"].lower()


def test_analyze_clothing_model_unavailable_returns_503(authenticated_client, monkeypatch):
    def fake_predict_clothing(image):
        raise clothing_analysis.ModelUnavailableError("no checkpoint")

    monkeypatch.setattr(clothing_analysis, "predict_clothing", fake_predict_clothing)

    files = {"file": ("item.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    response = authenticated_client.post("/analyze-clothing", files=files)

    assert response.status_code == 503


def test_analyze_clothing_invalid_image_rejected_before_model_call(authenticated_client, monkeypatch):
    """Invalid-image rejection happens in image_validation.py, before the
    (mocked-out) model is ever consulted — assert the mock is never called."""
    calls = []

    def fake_predict_clothing(image):
        calls.append(image)
        return {}

    monkeypatch.setattr(clothing_analysis, "predict_clothing", fake_predict_clothing)

    files = {"file": ("not-an-image.jpg", b"definitely not an image", "image/jpeg")}
    response = authenticated_client.post("/analyze-clothing", files=files)

    assert response.status_code == 400
    assert calls == []


# --- Phase 2: image-quality gate and structured color fields -----------------


def test_analyze_clothing_too_small_image_rejected_before_model_call(authenticated_client, monkeypatch):
    """Phase 2's hard-reject quality floor (MIN_HARD_DIMENSION) must run
    BEFORE the (mocked-out) model is ever consulted — a genuinely useless
    image shouldn't waste a model forward pass."""
    calls = []

    def fake_predict_clothing(image):
        calls.append(image)
        return {}

    monkeypatch.setattr(clothing_analysis, "predict_clothing", fake_predict_clothing)

    files = {"file": ("tiny.jpg", _valid_jpeg_bytes(size=(16, 16)), "image/jpeg")}
    response = authenticated_client.post("/analyze-clothing", files=files)

    assert response.status_code == 400
    assert "too small" in response.json()["detail"].lower()
    assert calls == []


def test_analyze_clothing_response_includes_phase2_structured_fields(authenticated_client, monkeypatch):
    def fake_predict_clothing(image):
        return {
            "category": "Tops",
            "confidence": 0.97,
            "low_confidence": False,
            "color": "Red",
            "color_confidence": 0.62,
            "secondary_color": "Black",
            "color_hex": "#aa2222",
            "color_reliability": "high",
            "segmentation_applied": True,
            "pattern": "solid",
            "brightness_level": "medium",
        }

    monkeypatch.setattr(clothing_analysis, "predict_clothing", fake_predict_clothing)

    files = {"file": ("shirt.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    response = authenticated_client.post("/analyze-clothing", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["secondary_color"] == "Black"
    assert body["color_hex"] == "#aa2222"
    assert body["color_reliability"] == "high"
    assert body["segmentation_applied"] is True
    assert body["pattern"] == "solid"
    assert body["brightness_level"] == "medium"
    # (quality_warnings itself is covered separately by the dedicated
    # low-quality-image tests in tests/test_image_quality.py and
    # test_analyze_clothing_too_small_image_rejected_before_model_call
    # above — this 64x64 solid-color fixture legitimately triggers its own
    # low-resolution/low-texture warnings, which isn't what this test is
    # checking.)
    assert isinstance(body["quality_warnings"], list)


def test_analyze_clothing_old_minimal_response_shape_still_works(authenticated_client, monkeypatch):
    """Backward-compatibility regression test: a mock that returns ONLY the
    original (pre-Phase-2) five keys must still produce a valid response —
    every new field has a default, nothing new is required."""

    def fake_predict_clothing(image):
        return {
            "category": "Tops",
            "confidence": 0.9,
            "low_confidence": False,
            "color": "Blue",
            "color_confidence": None,
        }

    monkeypatch.setattr(clothing_analysis, "predict_clothing", fake_predict_clothing)

    files = {"file": ("shirt.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    response = authenticated_client.post("/analyze-clothing", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "Tops"
    assert body["color"] == "Blue"
    assert body["secondary_color"] is None
    assert body["segmentation_applied"] is False


def test_unauthenticated_analyze_clothing_is_rejected(client):
    files = {"file": ("shirt.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    response = client.post("/analyze-clothing", files=files)
    assert response.status_code == 401
