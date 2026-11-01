"""Tests for ml/inference/image_quality.py (Phase 2). Verifies the
three-way outcome: invalid (hard reject), low-quality (accepted + warning),
normal (accepted, no warnings) — and that thresholds behave as documented."""

import numpy as np
import pytest
from PIL import Image

from ml.inference.image_quality import (
    BLUR_VARIANCE_THRESHOLD,
    BRIGHT_EXPOSURE_MIN,
    DARK_EXPOSURE_MAX,
    MIN_HARD_DIMENSION,
    RECOMMENDED_MIN_DIMENSION,
    ImageQualityError,
    assess_image_quality,
)


def _solid_image(size, color) -> Image.Image:
    return Image.new("RGB", size, color=color)


def _textured_image(size=(400, 400)) -> Image.Image:
    """A sharp, high-contrast checkerboard — the opposite of blurry."""
    array = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    block = 10
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if ((x // block) + (y // block)) % 2 == 0:
                array[y:y + block, x:x + block] = 255
    return Image.fromarray(array)


# --- Invalid: hard reject ----------------------------------------------------


def test_extremely_small_image_is_rejected():
    tiny = _solid_image((MIN_HARD_DIMENSION - 1, MIN_HARD_DIMENSION - 1), (128, 128, 128))
    with pytest.raises(ImageQualityError, match="too small"):
        assess_image_quality(tiny)


def test_image_at_exactly_the_hard_floor_is_accepted():
    boundary = _solid_image((MIN_HARD_DIMENSION, MIN_HARD_DIMENSION), (128, 128, 128))
    report = assess_image_quality(boundary)  # must not raise
    assert report.width == MIN_HARD_DIMENSION


# --- Low quality: accepted with a warning -------------------------------------


def test_low_resolution_image_is_accepted_with_a_warning():
    small = _solid_image((RECOMMENDED_MIN_DIMENSION - 10, RECOMMENDED_MIN_DIMENSION - 10), (128, 128, 128))
    report = assess_image_quality(small)
    assert any("resolution" in w.lower() for w in report.warnings)


def test_very_dark_image_is_accepted_with_a_warning():
    dark = _solid_image((300, 300), (DARK_EXPOSURE_MAX - 10,) * 3)
    report = assess_image_quality(dark)
    assert any("dark" in w.lower() for w in report.warnings)
    assert report.brightness is not None and report.brightness <= DARK_EXPOSURE_MAX


def test_overexposed_image_is_accepted_with_a_warning():
    bright = _solid_image((300, 300), (BRIGHT_EXPOSURE_MIN + 10,) * 3)
    report = assess_image_quality(bright)
    assert any("overexposed" in w.lower() for w in report.warnings)


def test_blurry_image_is_accepted_with_a_warning():
    # A perfectly uniform image has zero edges -> zero Laplacian variance ->
    # unambiguously "blurry" by this metric (there is no texture at all).
    flat = _solid_image((300, 300), (128, 128, 128))
    report = assess_image_quality(flat)
    assert report.blur_score == 0.0
    assert any("blurry" in w.lower() for w in report.warnings)
    assert report.blur_score < BLUR_VARIANCE_THRESHOLD


# --- Normal: accepted, no warnings --------------------------------------------


def test_normal_sized_sharp_well_exposed_image_has_no_warnings():
    image = _textured_image(size=(400, 400))
    report = assess_image_quality(image)
    assert report.warnings == []
    assert report.blur_score is not None and report.blur_score >= BLUR_VARIANCE_THRESHOLD


# --- Corrupted / invalid files ------------------------------------------------
# (Decode-time corruption is rejected earlier, in
#  app/services/image_validation.py, before a PIL Image object even
#  exists — covered by tests/test_wardrobe_api.py's
#  test_upload_invalid_image_content_rejected. assess_image_quality() only
#  ever receives an already-successfully-decoded PIL Image, so there is no
#  separate "corrupted file" case to test at this layer.)


def test_report_is_always_well_formed_even_with_many_simultaneous_warnings():
    """A tiny, dark, blurry (but not hard-reject-small) image should
    accumulate multiple warnings without crashing or losing any of them."""
    image = _solid_image((RECOMMENDED_MIN_DIMENSION - 50, RECOMMENDED_MIN_DIMENSION - 50), (10, 10, 10))
    report = assess_image_quality(image)

    assert len(report.warnings) >= 2
    assert all(isinstance(w, str) and w for w in report.warnings)
