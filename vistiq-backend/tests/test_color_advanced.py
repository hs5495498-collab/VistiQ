"""Tests for ml/inference/color_advanced.py (Phase 2: K-means color
clustering over HSV, foreground-aware when segmentation succeeds).

K-means here is an UNSUPERVISED CLUSTERING algorithm used as a classical
image-processing step — it is not a trained/learned model, and these tests
treat it accordingly (checking deterministic, explainable behavior, not
"accuracy" against labeled ground truth the way the MobileNet classifier
tests do)."""

import sys

import numpy as np
from PIL import Image

from ml.inference import color_advanced
from ml.inference.segmentation import SegmentationResult


def _solid_image(size=(100, 100), color=(20, 20, 20)) -> Image.Image:
    return Image.new("RGB", size, color=color)


def _two_region_image(size=(120, 120), bg_color=(40, 170, 60), fg_color=(210, 30, 30), fg_box=(30, 30, 90, 90)) -> Image.Image:
    """A large background region plus a smaller, centered foreground box
    of a visibly different color — background-vs-foreground color
    contrast is exactly what segmentation is supposed to help with."""
    image = Image.new("RGB", size, color=bg_color)
    x0, y0, x1, y1 = fg_box
    for y in range(y0, y1):
        for x in range(x0, x1):
            image.putpixel((x, y), fg_color)
    return image


def _mask_for_box(size, box) -> np.ndarray:
    mask = np.zeros((size[1], size[0]), dtype=bool)
    x0, y0, x1, y1 = box
    mask[y0:y1, x0:x1] = True
    return mask


# --- RGB -> HSV conversion (exercised indirectly, verified directly here) ---


def test_rgb_to_hsv_conversion_is_correct():
    """Sanity-check the exact conversion math color_advanced.py relies on
    (via cv2.cvtColor) independently of the clustering logic around it."""
    import cv2

    pure_red_bgr = np.array([[[0, 0, 255]]], dtype=np.uint8)  # OpenCV is BGR
    hsv = cv2.cvtColor(pure_red_bgr, cv2.COLOR_BGR2HSV)[0, 0]
    # Pure red: hue ~0, full saturation, full value.
    assert hsv[0] in (0, 179)  # hue wraps at both ends of the red band
    assert hsv[1] == 255
    assert hsv[2] == 255


# --- Determinism --------------------------------------------------------------


def test_extract_color_profile_is_deterministic_for_identical_input():
    image = _two_region_image()
    first = color_advanced.extract_color_profile(image, None)
    second = color_advanced.extract_color_profile(image, None)

    assert first.primary.name == second.primary.name
    assert first.primary.rgb == second.primary.rgb
    assert first.primary.percentage == second.primary.percentage
    assert first.pattern == second.pattern
    assert first.brightness_level == second.brightness_level


# --- Monochrome / multicolor ---------------------------------------------------


def test_monochrome_image_has_no_significant_secondary_color():
    image = _solid_image(color=(25, 25, 28))  # a near-black solid garment
    profile = color_advanced.extract_color_profile(image, None)

    assert profile.primary.name == "Black"
    assert profile.secondary is None
    assert profile.pattern in {"solid", "unknown"}


def test_multicolor_image_detects_a_distinct_secondary_color():
    image = _two_region_image(bg_color=(230, 230, 20), fg_color=(20, 30, 220))  # yellow-ish + blue
    # No segmentation here — both regions are large enough to each clear
    # the significance threshold on their own.
    profile = color_advanced.extract_color_profile(image, None)

    assert profile.secondary is not None
    assert profile.secondary.name != profile.primary.name
    assert profile.secondary.percentage >= color_advanced.SECONDARY_COLOR_MIN_PERCENTAGE


def test_insignificant_minor_cluster_is_not_reported_as_secondary():
    """A tiny sliver of a different color (a few stray pixels) must not
    surface as a 'secondary color' — only clusters above
    SECONDARY_COLOR_MIN_PERCENTAGE count."""
    image = _solid_image(size=(100, 100), color=(220, 220, 225))
    for x in range(3):  # a handful of stray pixels, well under the threshold
        image.putpixel((x, 0), (0, 0, 0))

    profile = color_advanced.extract_color_profile(image, None)

    assert profile.secondary is None


# --- Background influence vs. successful segmentation -------------------------


def test_background_dominates_without_segmentation_when_not_near_white():
    """Documents the exact Phase 1 limitation Phase 2 exists to fix: a
    non-white background larger than the garment currently wins, because
    the only background filter is 'is it near-white'."""
    image = _two_region_image()  # green background, smaller red foreground box
    profile = color_advanced.extract_color_profile(image, None)

    assert profile.primary.name == "Green"


def test_successful_segmentation_prevents_background_from_dominating():
    """The same image as above, but now with a (hand-constructed, as if
    GrabCut had succeeded) mask isolating just the foreground box — the
    garment's own color must now win instead of the larger background."""
    size = (120, 120)
    fg_box = (30, 30, 90, 90)
    image = _two_region_image(size=size, fg_box=fg_box)
    mask = _mask_for_box(size, fg_box)
    segmentation_result = SegmentationResult(
        success=True, mask=mask, foreground_fraction=float(mask.mean()),
        method="grabcut", detail="synthetic mask for testing",
    )

    profile = color_advanced.extract_color_profile(image, segmentation_result)

    assert profile.primary.name == "Red"
    assert profile.segmentation_applied is True


def test_failed_segmentation_result_falls_back_to_background_inclusive_sample():
    """A SegmentationResult with success=False must be treated exactly
    like no segmentation at all — never trusted, per its own contract."""
    image = _two_region_image()
    failed_segmentation = SegmentationResult(
        success=False, mask=None, foreground_fraction=None, method="failed", detail="simulated failure",
    )

    with_failed = color_advanced.extract_color_profile(image, failed_segmentation)
    without_any = color_advanced.extract_color_profile(image, None)

    assert with_failed.primary.name == without_any.primary.name
    assert with_failed.segmentation_applied is False


# --- Deterministic fallback (K-means unavailable / degenerate input) ---------


def test_falls_back_to_deterministic_method_when_opencv_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "cv2", None)  # forces `import cv2` to raise ImportError

    image = _solid_image(color=(15, 15, 15))
    profile = color_advanced.extract_color_profile(image, None)

    assert profile.method == "deterministic_fallback"
    assert profile.primary.name == "Black"
    assert profile.reliability == "low"


def test_fallback_result_is_never_empty_or_invalid():
    """Contract check across both the main path and the fallback path:
    a ColorProfile is always well-formed — a named primary color, a valid
    hex string, and a non-empty clusters list."""
    for image in (_solid_image(), _two_region_image(), Image.new("RGB", (40, 40), (255, 255, 255))):
        profile = color_advanced.extract_color_profile(image, None)
        assert profile.primary.name
        assert profile.primary.hex.startswith("#") and len(profile.primary.hex) == 7
        assert len(profile.clusters) >= 1
        assert profile.reliability in {"high", "medium", "low"}
        assert profile.pattern in {"solid", "patterned", "unknown"}
        assert profile.brightness_level in {"light", "medium", "dark", "unknown"}
