"""
Image quality assessment for the clothing-analysis pipeline — Phase 2.

Three-way outcome, per the project's explicit requirement:
  - Invalid:      reject with a useful error (ImageQualityError), BEFORE
                  running the classifier — currently only "too small to
                  analyze at all." Content-type/size/corrupt-file checks
                  already happen earlier, in
                  app/services/image_validation.py, and are untouched.
  - Low-quality:  accepted, but `assess_image_quality()` returns one or
                  more human-readable warnings for the caller to surface
                  (e.g. in the API response's `quality_warnings` field).
  - Normal:       accepted, zero warnings.

All thresholds below are named constants with a stated justification, not
unexplained magic numbers, and are easy to retune in one place.
"""

from dataclasses import dataclass, field

import numpy as np
from PIL import Image

# --- Hard floor (reject) -----------------------------------------------------

# Below this on either side, there is no usable visual signal left to
# classify or color-analyze — not a real clothing photo, likely a thumbnail,
# icon, or corrupted/truncated decode.
MIN_HARD_DIMENSION = 32

# --- Soft floor (warn only) ---------------------------------------------------

# The classifier resizes every image to 224x224 (ml/training/config.py's
# IMAGE_SIZE) regardless of input size. Below this, the image is being
# upscaled rather than downscaled for that resize, which can soften detail
# the model would otherwise use — worth a warning, not a rejection.
RECOMMENDED_MIN_DIMENSION = 224

# --- Blur (warn only) ---------------------------------------------------------

# Variance of the Laplacian is a standard, well-established blur metric
# (the "Laplacian variance" method) — low variance means few sharp edges,
# which usually means a blurry photo. Measured AFTER resizing to a fixed
# size (BLUR_CHECK_SIZE) specifically so the threshold doesn't depend on
# the original photo's resolution (a larger photo naturally has more raw
# edge pixels even at the same effective sharpness).
BLUR_CHECK_SIZE = (300, 300)
BLUR_VARIANCE_THRESHOLD = 60.0

# --- Exposure (warn only) -----------------------------------------------------

# Mean grayscale brightness, 0-255 scale.
DARK_EXPOSURE_MAX = 35
BRIGHT_EXPOSURE_MIN = 230


class ImageQualityError(ValueError):
    """Raised for a hard-reject case (currently: too small to analyze).
    Caught by app/routes/clothing_analysis.py and turned into an HTTP 400 —
    mirrors the existing ModelUnavailableError -> 503 pattern."""


@dataclass
class ImageQualityReport:
    width: int
    height: int
    blur_score: float | None
    brightness: float | None
    warnings: list[str] = field(default_factory=list)


def assess_image_quality(image: Image.Image) -> ImageQualityReport:
    """Raises ImageQualityError for the one hard-reject case; otherwise
    always returns a populated report (warnings may be empty)."""
    width, height = image.size

    if width < MIN_HARD_DIMENSION or height < MIN_HARD_DIMENSION:
        raise ImageQualityError(
            f"Image is too small to analyze reliably ({width}x{height}px); "
            f"minimum is {MIN_HARD_DIMENSION}x{MIN_HARD_DIMENSION}px."
        )

    warnings: list[str] = []
    if width < RECOMMENDED_MIN_DIMENSION or height < RECOMMENDED_MIN_DIMENSION:
        warnings.append(
            f"Image resolution is low ({width}x{height}px) — it will be "
            "upscaled for analysis, which may reduce prediction quality."
        )

    grayscale = np.asarray(image.convert("L"), dtype=np.float64)
    brightness = float(grayscale.mean())
    if brightness <= DARK_EXPOSURE_MAX:
        warnings.append("Image appears very dark — consider retaking it with better lighting.")
    elif brightness >= BRIGHT_EXPOSURE_MIN:
        warnings.append("Image appears overexposed — consider retaking it with less direct light.")

    blur_score = _laplacian_variance(image)
    if blur_score is not None and blur_score < BLUR_VARIANCE_THRESHOLD:
        warnings.append("Image appears blurry — classification confidence may be reduced.")

    return ImageQualityReport(width=width, height=height, blur_score=blur_score, brightness=brightness, warnings=warnings)


def _laplacian_variance(image: Image.Image) -> float | None:
    """Returns None (never raises) if OpenCV is unavailable — blur
    detection is a nice-to-have warning, not something worth failing the
    whole quality assessment over."""
    try:
        import cv2
    except ImportError:
        return None

    resized = image.convert("L").resize(BLUR_CHECK_SIZE)
    laplacian = cv2.Laplacian(np.asarray(resized), cv2.CV_64F)
    return float(laplacian.var())
