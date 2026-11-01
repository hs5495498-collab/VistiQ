"""
Deterministic dominant-color extraction — NOT machine learning.

This is plain image processing: quantize the image to a small palette,
find the most common resulting color, ignore near-white/near-black
background pixels, and snap the result to VISTIQ's supported color buckets
by nearest distance in RGB space. Given the same image, this always returns
the same color — there is no learned model and no "confidence" in the ML
sense, which is why predict_clothing() reports color_confidence as null.

Pipeline (explainable step by step):
    image -> resize small (speed) -> drop near-white background pixels
          -> palette quantization -> most common palette color
          -> nearest VISTIQ color bucket
"""

from PIL import Image

from ml.training.config import COLOR_PALETTE

THUMBNAIL_SIZE = (120, 120)
PALETTE_COLORS = 8
# Pixels this close to pure white are treated as background/studio backdrop,
# not garment color, and excluded from the dominant-color vote.
BACKGROUND_WHITE_THRESHOLD = 235


def _color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _nearest_vistiq_color(rgb: tuple[int, int, int]) -> str:
    best_name, best_distance = None, float("inf")
    for name, bucket_rgb in COLOR_PALETTE.items():
        distance = _color_distance(rgb, tuple(bucket_rgb))
        if distance < best_distance:
            best_name, best_distance = name, distance
    return best_name


def nearest_vistiq_color(rgb: tuple[int, int, int]) -> str:
    """Public alias of `_nearest_vistiq_color` — reused by
    ml/inference/color_advanced.py (Phase 2) so both the original
    deterministic pipeline and the newer K-means pipeline snap to the exact
    same named color palette, rather than each maintaining its own copy."""
    return _nearest_vistiq_color(rgb)


def extract_dominant_color(image: Image.Image) -> tuple[str, tuple[int, int, int]]:
    """Returns (vistiq_color_name, dominant_rgb)."""
    rgb_image = image.convert("RGB")
    rgb_image.thumbnail(THUMBNAIL_SIZE)

    pixels = list(rgb_image.getdata())
    foreground_pixels = [
        p for p in pixels
        if not (p[0] > BACKGROUND_WHITE_THRESHOLD
                and p[1] > BACKGROUND_WHITE_THRESHOLD
                and p[2] > BACKGROUND_WHITE_THRESHOLD)
    ]

    # If the whole image looks like background (e.g. a mostly-white/blank
    # photo), fall back to using every pixel rather than crashing on an
    # empty selection.
    sample_pixels = foreground_pixels if foreground_pixels else pixels

    sample_image = Image.new("RGB", (len(sample_pixels), 1))
    sample_image.putdata(sample_pixels)

    quantized = sample_image.quantize(colors=PALETTE_COLORS, method=Image.MEDIANCUT)
    palette = quantized.getpalette()
    color_counts = quantized.getcolors()  # [(count, palette_index), ...]
    dominant_index = max(color_counts, key=lambda item: item[0])[1]

    r = palette[dominant_index * 3]
    g = palette[dominant_index * 3 + 1]
    b = palette[dominant_index * 3 + 2]
    dominant_rgb = (r, g, b)

    return _nearest_vistiq_color(dominant_rgb), dominant_rgb
