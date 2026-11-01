"""
Structured dominant-color extraction — Phase 2.

Still NOT machine learning. K-means is an unsupervised clustering
algorithm used here as a classical image-processing step (grouping pixels
by color similarity) — it is not trained on labeled data, has no notion of
"garment" vs "background" on its own, and is not a predictive model in the
sense MobileNetV3 (ml/inference/predict.py) is. Any "confidence"-shaped
number this module produces is a cluster-dominance/segmentation-reliability
score, not an ML confidence value — see ColorProfile.reliability below.

Pipeline:
    image -> (optional) foreground mask from segmentation.py
          -> pixel sample (foreground-only if available, else the Phase 1
             near-white-background heuristic from color.py)
          -> convert sample to HSV
          -> K-means cluster the HSV pixels (k=KMEANS_CLUSTERS)
          -> drop clusters below SECONDARY_COLOR_MIN_PERCENTAGE significance
          -> map the top 1-2 surviving clusters' RGB centers to VISTIQ's
             named color palette (ml/inference/color.py's shared mapping)
          -> also derive `pattern` and `brightness_level` from the same
             cluster/HSV data, at no extra computation cost

Falls back to the original Phase 1 `color.extract_dominant_color()`
whenever anything here can't produce a trustworthy result (K-means failure,
degenerate input, OpenCV unavailable) — the old function is never removed
or bypassed entirely, exactly so that fallback is possible.
"""

from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from ml.inference import color as deterministic_color
from ml.inference.segmentation import SegmentationResult

KMEANS_CLUSTERS = 5
KMEANS_ATTEMPTS = 3
KMEANS_MAX_ITER = 20
KMEANS_EPSILON = 1.0

# cv2.kmeans's KMEANS_PP_CENTERS initialization draws from OpenCV's global
# RNG. Without fixing its seed, the exact same input image could produce
# different cluster centers/ordering on different calls — unacceptable for
# a project requirement that identical inputs give identical outputs.
# Reseeding to the same fixed value immediately before every kmeans call
# makes the clustering itself deterministic.
KMEANS_RNG_SEED = 42

# A cluster covering less than this share of sampled pixels is treated as
# visual noise (stray highlight/shadow/stitching pixels), not a meaningful
# secondary garment color.
SECONDARY_COLOR_MIN_PERCENTAGE = 0.15

# Primary cluster dominance thresholds used only for the `pattern` heuristic
# (see _infer_pattern) — not reliability scoring.
SOLID_DOMINANCE_THRESHOLD = 0.70

# Mean HSV "V" (brightness) thresholds, 0-255 scale, for `brightness_level`.
DARK_BRIGHTNESS_MAX = 85
LIGHT_BRIGHTNESS_MIN = 170


@dataclass
class ColorCluster:
    name: str
    rgb: tuple[int, int, int]
    hex: str
    percentage: float


@dataclass
class ColorProfile:
    primary: ColorCluster
    secondary: ColorCluster | None
    reliability: str  # "high" | "medium" | "low"
    segmentation_applied: bool
    pattern: str  # "solid" | "patterned" | "unknown"
    brightness_level: str  # "light" | "medium" | "dark" | "unknown"
    method: str  # "kmeans" | "deterministic_fallback"
    clusters: list[ColorCluster] = field(default_factory=list)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _foreground_pixel_sample(rgb_image: Image.Image, segmentation: SegmentationResult | None) -> np.ndarray:
    """Returns an (N, 3) uint8 RGB array of the pixels to analyze — the
    segmented foreground when available and successful, otherwise the
    Phase 1 near-white-background heuristic (same rule as
    color.extract_dominant_color, kept in sync by calling into the same
    constants rather than duplicating the threshold)."""
    thumbnail = rgb_image.copy()
    thumbnail.thumbnail(deterministic_color.THUMBNAIL_SIZE)
    pixels = np.array(thumbnail).reshape(-1, 3)

    if segmentation is not None and segmentation.success and segmentation.mask is not None:
        mask_image = Image.fromarray(segmentation.mask.astype(np.uint8) * 255)
        mask_image = mask_image.resize(thumbnail.size, resample=Image.NEAREST)
        mask = np.array(mask_image).reshape(-1) > 0
        foreground = pixels[mask]
        if foreground.size > 0:
            return foreground
        # Segmentation claimed success but produced zero pixels at thumbnail
        # resolution (can happen for a very thin mask shrunk aggressively) —
        # fall through to the deterministic heuristic below rather than
        # return an empty sample.

    threshold = deterministic_color.BACKGROUND_WHITE_THRESHOLD
    not_white = ~np.all(pixels > threshold, axis=1)
    foreground = pixels[not_white]
    return foreground if foreground.size > 0 else pixels


def _infer_pattern(clusters: list[ColorCluster]) -> str:
    """Solid vs. patterned, from how concentrated the clustering is —
    grouped by VISTIQ color NAME first, not raw cluster percentage.
    Without this grouping, a genuinely solid garment photographed with
    ordinary shading (e.g. two clusters that both map to "Black" — one for
    the lit area, one for the shadow) would incorrectly count as two
    separate significant colors and get called "patterned"."""
    if not clusters:
        return "unknown"

    name_totals: dict[str, float] = {}
    for cluster in clusters:
        name_totals[cluster.name] = name_totals.get(cluster.name, 0.0) + cluster.percentage

    totals = sorted(name_totals.values(), reverse=True)
    if totals[0] >= SOLID_DOMINANCE_THRESHOLD:
        return "solid"
    significant = [t for t in totals if t >= SECONDARY_COLOR_MIN_PERCENTAGE]
    if len(significant) >= 2:
        return "patterned"
    return "unknown"


def _infer_brightness(mean_value: float) -> str:
    if mean_value <= DARK_BRIGHTNESS_MAX:
        return "dark"
    if mean_value >= LIGHT_BRIGHTNESS_MIN:
        return "light"
    return "medium"


def _kmeans_fallback(image: Image.Image, segmentation: SegmentationResult | None) -> ColorProfile:
    """Phase 1's deterministic method, wrapped in the Phase 2 structured
    shape so callers always get a ColorProfile regardless of which path
    actually ran."""
    color_name, rgb = deterministic_color.extract_dominant_color(image)
    cluster = ColorCluster(name=color_name, rgb=rgb, hex=_rgb_to_hex(rgb), percentage=1.0)
    return ColorProfile(
        primary=cluster,
        secondary=None,
        reliability="low",
        segmentation_applied=bool(segmentation and segmentation.success),
        pattern="unknown",
        brightness_level="unknown",
        method="deterministic_fallback",
        clusters=[cluster],
    )


def extract_color_profile(
    image: Image.Image, segmentation: SegmentationResult | None = None
) -> ColorProfile:
    """Main Phase 2 entry point. Never raises and never returns an empty/
    invalid profile — any internal failure falls back to
    `_kmeans_fallback()`, which itself falls back to the Phase 1
    deterministic method."""
    try:
        import cv2
    except ImportError:
        return _kmeans_fallback(image, segmentation)

    rgb_image = image.convert("RGB")
    sample_rgb = _foreground_pixel_sample(rgb_image, segmentation)
    if sample_rgb.shape[0] < KMEANS_CLUSTERS:
        # Not enough distinct pixels to meaningfully cluster (e.g. a tiny
        # or near-uniform sample) — the deterministic method handles this
        # case fine on its own.
        return _kmeans_fallback(image, segmentation)

    try:
        sample_bgr = sample_rgb[:, ::-1].astype(np.uint8).reshape(-1, 1, 3)
        sample_hsv = cv2.cvtColor(sample_bgr, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, KMEANS_MAX_ITER, KMEANS_EPSILON)
        cv2.setRNGSeed(KMEANS_RNG_SEED)
        _compactness, labels, centers_hsv = cv2.kmeans(
            sample_hsv, KMEANS_CLUSTERS, None, criteria, KMEANS_ATTEMPTS, cv2.KMEANS_PP_CENTERS
        )
        labels = labels.reshape(-1)
    except cv2.error:
        return _kmeans_fallback(image, segmentation)

    total_pixels = labels.shape[0]
    counts = np.bincount(labels, minlength=KMEANS_CLUSTERS)
    percentages = counts / total_pixels

    centers_hsv_uint8 = np.clip(centers_hsv, 0, 255).astype(np.uint8).reshape(-1, 1, 3)
    centers_bgr = cv2.cvtColor(centers_hsv_uint8, cv2.COLOR_HSV2BGR).reshape(-1, 3)
    centers_rgb = centers_bgr[:, ::-1]

    order = np.argsort(-percentages)
    clusters: list[ColorCluster] = []
    for index in order:
        if counts[index] == 0:
            continue
        rgb = tuple(int(c) for c in centers_rgb[index])
        name = deterministic_color.nearest_vistiq_color(rgb)
        clusters.append(ColorCluster(name=name, rgb=rgb, hex=_rgb_to_hex(rgb), percentage=round(float(percentages[index]), 4)))

    if not clusters:
        return _kmeans_fallback(image, segmentation)

    primary = clusters[0]
    secondary = None
    for candidate in clusters[1:]:
        if candidate.percentage >= SECONDARY_COLOR_MIN_PERCENTAGE and candidate.name != primary.name:
            secondary = candidate
            break

    segmentation_applied = bool(segmentation and segmentation.success)
    if segmentation_applied and primary.percentage >= 0.40:
        reliability = "high"
    elif segmentation_applied or primary.percentage >= 0.40:
        reliability = "medium"
    else:
        reliability = "low"

    pattern = _infer_pattern(clusters)
    mean_value = float(np.mean(sample_hsv[:, 2])) if sample_hsv.size else 0.0
    brightness_level = _infer_brightness(mean_value)

    return ColorProfile(
        primary=primary,
        secondary=secondary,
        reliability=reliability,
        segmentation_applied=segmentation_applied,
        pattern=pattern,
        brightness_level=brightness_level,
        method="kmeans",
        clusters=clusters,
    )
