"""
Foreground/background segmentation for garment photos — Phase 2.

Uses OpenCV's GrabCut: a classical, iterative energy-minimization algorithm
(Rother, Kolmogorov & Blake, 2004). It is NOT a trained/learned model — no
weights are downloaded, nothing is fine-tuned, and results depend only on
the image it's given each time (deterministic for a fixed input + fixed
rect seed + fixed iteration count).

Why GrabCut over a pretrained segmentation network (e.g. U2-Net/rembg):
cheaper to install (ships inside opencv-python-headless, no separate model
download), pure CPU, fast enough once the image is downscaled first (see
SEGMENTATION_MAX_DIMENSION below), and good enough for the flat-lay/product
style photos this project's wardrobe uploads actually look like. It is NOT
a general-purpose, robust segmenter — see the limitations in the module
docstring at the bottom of this file.

Seed assumption: the garment is roughly centered with background nearer the
image edges — true for flat-lay/product photography, not true for e.g. a
garment worn by a person filling the whole frame. When that assumption
doesn't hold, the foreground-fraction sanity check below is what catches it
and reports failure rather than returning a wrong mask silently.
"""

from dataclasses import dataclass

import numpy as np
from PIL import Image

# Full-resolution GrabCut is far too slow for a synchronous API request —
# measured up to 74s on a single real 860x1290 upload in this project.
# Downscaling the longest edge to this size before running GrabCut, then
# upscaling the resulting mask back to the original size, brought that down
# to 0.3-1.8s on the same real uploads while keeping foreground fractions in
# a sane, non-degenerate range. This is a standard GrabCut performance
# practice, not a VISTIQ-specific hack.
SEGMENTATION_MAX_DIMENSION = 300

GRABCUT_ITERATIONS = 5

# Fraction of the (downscaled) image assumed to be background margin on
# every side when seeding GrabCut's initial rectangle — i.e. the garment is
# assumed to occupy the central 84% of the frame. Matches typical flat-lay/
# product photography framing.
GRABCUT_RECT_MARGIN_FRACTION = 0.08

# If the resulting foreground mask covers less than this fraction of the
# image, GrabCut likely collapsed to "almost nothing is foreground" —
# treat as a failed segmentation rather than trust a near-empty mask.
MIN_FOREGROUND_FRACTION = 0.05

# If the resulting foreground mask covers more than this fraction, GrabCut
# likely failed to separate anything from the background at all (e.g. a
# background that's visually similar to the garment) — also treat as failed.
MAX_FOREGROUND_FRACTION = 0.95


@dataclass
class SegmentationResult:
    """Result of attempting foreground segmentation on one image.

    `mask` is a boolean numpy array the same size as the ORIGINAL image
    (height, width) — True where the pixel is believed to be garment
    foreground. It is None whenever `success` is False, by design: callers
    must check `success` rather than trust a possibly-meaningless mask.
    """

    success: bool
    mask: np.ndarray | None
    foreground_fraction: float | None
    method: str  # "grabcut" | "failed" | "unavailable"
    detail: str  # short, human-readable reason — always populated, never empty


def segment_foreground(image: Image.Image) -> SegmentationResult:
    """Attempt GrabCut foreground segmentation on a PIL image.

    Never raises — any failure (OpenCV error, degenerate mask, missing
    dependency) is reported through `SegmentationResult.success = False`
    with a populated `detail`, so a caller always gets a well-formed,
    non-empty result object to make a fallback decision from.
    """
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover — opencv is a declared
        # hard dependency (requirements.txt); this only guards against a
        # genuinely broken/incomplete environment rather than silently
        # crashing the whole analysis request.
        return SegmentationResult(
            success=False, mask=None, foreground_fraction=None,
            method="unavailable", detail=f"OpenCV unavailable: {exc}",
        )

    rgb_image = image.convert("RGB")
    width, height = rgb_image.size
    if width < 10 or height < 10:
        return SegmentationResult(
            success=False, mask=None, foreground_fraction=None,
            method="failed", detail="Image too small for segmentation.",
        )

    bgr_full = np.array(rgb_image)[:, :, ::-1].copy()  # PIL RGB -> OpenCV BGR

    scale = min(1.0, SEGMENTATION_MAX_DIMENSION / max(width, height))
    if scale < 1.0:
        small_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        bgr_small = cv2.resize(bgr_full, small_size, interpolation=cv2.INTER_AREA)
    else:
        bgr_small = bgr_full

    small_h, small_w = bgr_small.shape[:2]
    margin_x = max(1, round(small_w * GRABCUT_RECT_MARGIN_FRACTION))
    margin_y = max(1, round(small_h * GRABCUT_RECT_MARGIN_FRACTION))
    rect_w = small_w - 2 * margin_x
    rect_h = small_h - 2 * margin_y
    if rect_w <= 0 or rect_h <= 0:
        return SegmentationResult(
            success=False, mask=None, foreground_fraction=None,
            method="failed", detail="Image too small/narrow to seed a GrabCut rectangle.",
        )
    rect = (margin_x, margin_y, rect_w, rect_h)

    cv2_mask = np.zeros((small_h, small_w), np.uint8)
    bg_model = np.zeros((1, 65), np.float64)
    fg_model = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(bgr_small, cv2_mask, rect, bg_model, fg_model, GRABCUT_ITERATIONS, cv2.GC_INIT_WITH_RECT)
    except cv2.error as exc:
        return SegmentationResult(
            success=False, mask=None, foreground_fraction=None,
            method="failed", detail=f"GrabCut raised an error: {exc}",
        )

    small_fg_mask = (cv2_mask == cv2.GC_FGD) | (cv2_mask == cv2.GC_PR_FGD)
    foreground_fraction = float(small_fg_mask.mean())

    if not (MIN_FOREGROUND_FRACTION <= foreground_fraction <= MAX_FOREGROUND_FRACTION):
        return SegmentationResult(
            success=False, mask=None, foreground_fraction=foreground_fraction,
            method="failed",
            detail=(
                f"Foreground fraction {foreground_fraction:.1%} outside the "
                f"sane [{MIN_FOREGROUND_FRACTION:.0%}, {MAX_FOREGROUND_FRACTION:.0%}] "
                "range — treating as a degenerate/failed segmentation."
            ),
        )

    if scale < 1.0:
        full_mask = cv2.resize(
            small_fg_mask.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST
        ).astype(bool)
    else:
        full_mask = small_fg_mask

    return SegmentationResult(
        success=True, mask=full_mask, foreground_fraction=foreground_fraction,
        method="grabcut",
        detail=f"GrabCut succeeded, foreground covers {foreground_fraction:.1%} of the image.",
    )


# Known limitations (deliberately not hidden):
#
# - Assumes a roughly centered garment with background nearer the edges.
#   A garment photographed off-center, cropped tight to the frame, or worn
#   by a person filling the whole image will likely fail the foreground-
#   fraction sanity check and fall back to the Phase 1 deterministic color
#   heuristic (see ml/inference/color_advanced.py) rather than produce a
#   wrong mask.
# - Complex/cluttered or low-contrast backgrounds (background color close to
#   the garment's own color) reduce GrabCut's accuracy — it is a classical
#   algorithm, not a learned, context-aware segmenter.
# - Downscaling before segmentation (for speed) trades a small amount of
#   mask boundary precision for a ~40-200x speedup — acceptable here
#   because the mask is only used to pick which pixels feed color
#   extraction, not for any pixel-perfect cropping/display use.
