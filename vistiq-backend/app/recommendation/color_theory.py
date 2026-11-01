"""
Fashion color-theory compatibility — Phase 3.

Builds on ml/labels/clothing_categories.json's COLOR_PALETTE (the same 14
named colors used everywhere else in VISTIQ — Phase 2 color extraction, the
Add Item color picker) rather than inventing a separate palette. For each
named color, this module derives its HSV hue once, using `colorsys`
(Python's own standard library — no new dependency), and classifies it as
"neutral" (reusing app/recommendation/rules.py's existing NEUTRAL_COLORS
set — single source of truth, never duplicated) or "chromatic" (has a
meaningful hue).

Why hue-wheel relationships instead of only RGB distance: RGB Euclidean
distance measures numeric closeness, not fashion harmony — navy and black
are RGB-close but navy and white is the classic high-harmony pairing, which
is RGB-far. Real color theory instead asks: are two colors opposite on the
hue wheel (complementary — bold, high-contrast), adjacent (analogous —
calm, coordinated), identical (monochromatic), or neutral (pairs with
almost anything)? This module computes exactly that, but checks the
specific classic pairings already proven in rules.py's HIGH_COLOR_PAIRS /
GOOD_COLOR_PAIRS tables FIRST, since those are established fashion rules
that don't purely follow hue math (e.g. navy+beige isn't a hue-wheel
relationship, it's just a known-good pairing) — this module extends that
existing table with general-purpose hue math for everything it doesn't
already cover, rather than replacing it.
"""

import colorsys

from app.database.models import ClothingItem
from app.recommendation import rules
from ml.training.config import COLOR_PALETTE

# --- Hue-wheel thresholds, in degrees (0-360 hue circle) --------------------

ANALOGOUS_MAX_DEGREES = 40.0
COMPLEMENTARY_MIN_DEGREES = 150.0
COMPLEMENTARY_MAX_DEGREES = 210.0

# --- Scores for relationships not already in rules.py's classic tables -----

MONOCHROMATIC_SCORE = 0.75
COMPLEMENTARY_SCORE = 0.85
ANALOGOUS_SCORE = 0.80
CONTRASTING_SCORE = 0.50  # neither classic rule nor a clean hue relationship — genuinely uncertain
UNKNOWN_COLOR_SCORE = 0.45  # a color name outside VISTIQ's 14-color palette (e.g. free-text manual entry)

# --- Reliability down-weighting ---------------------------------------------
#
# How much a pair's computed score gets pulled toward a neutral 0.5 ("we
# don't actually know") when color reliability is reduced. 0.0 = trust the
# color fully; 1.0 = ignore it entirely. "high" and the Python value `None`
# (unknown — every item created before this column existed, or any
# manually-entered item with no photo analysis) are BOTH full weight:
# unknown reliability must never be treated as if it were known-bad.
RELIABILITY_BLEND: dict[str | None, float] = {"high": 0.0, "medium": 0.35, "low": 0.75, None: 0.0}


def _hue_degrees(rgb: list[int]) -> float:
    r, g, b = (channel / 255.0 for channel in rgb)
    hue, _saturation, _value = colorsys.rgb_to_hsv(r, g, b)
    return hue * 360.0


# Computed once at import time from the single source of truth
# (ml/labels/clothing_categories.json) — never hardcoded separately, so it
# can never drift out of sync with the actual palette.
#
# Known edge case, deliberately not a bug: HSV hue is mathematically
# undefined for a near-zero-saturation color — Black ([24,24,27]) and
# White ([244,244,245]) both happen to come out of colorsys at the same
# arbitrary hue (240 degrees) despite being opposite in every way that
# matters. This is harmless in practice ONLY because is_neutral() /
# hue_relationship() always special-case neutrals out before any hue
# comparison is made — exactly why neutrality (desaturation) and hue are
# treated as two separate questions in this module, not one.
_HUE_BY_NAME: dict[str, float] = {name.lower(): _hue_degrees(rgb) for name, rgb in COLOR_PALETTE.items()}


def is_neutral(color_name: str | None) -> bool:
    if not color_name:
        return False
    return color_name.strip().lower() in rules.NEUTRAL_COLORS


def _hue_difference(hue_a: float, hue_b: float) -> float:
    """Shortest distance between two hues on a 360-degree circle (e.g. the
    difference between 10 degrees and 350 degrees is 20, not 340)."""
    raw_difference = abs(hue_a - hue_b) % 360.0
    return min(raw_difference, 360.0 - raw_difference)


def hue_relationship(color_a: str, color_b: str) -> str | None:
    """Classifies two CHROMATIC (non-neutral) color names by their position
    on the hue wheel: "monochromatic" (same color), "complementary"
    (roughly opposite), "analogous" (close together), or "contrasting"
    (neither). Returns None if either name isn't in VISTIQ's known
    palette, or either one is neutral — neutrals have no meaningful hue to
    compare."""
    a, b = color_a.strip().lower(), color_b.strip().lower()
    if a not in _HUE_BY_NAME or b not in _HUE_BY_NAME:
        return None
    if is_neutral(a) or is_neutral(b):
        return None
    if a == b:
        return "monochromatic"

    difference = _hue_difference(_HUE_BY_NAME[a], _HUE_BY_NAME[b])
    if COMPLEMENTARY_MIN_DEGREES <= difference <= COMPLEMENTARY_MAX_DEGREES:
        return "complementary"
    if difference <= ANALOGOUS_MAX_DEGREES:
        return "analogous"
    return "contrasting"


def base_color_pair_score(color_a: str | None, color_b: str | None) -> tuple[float, str]:
    """The core (reliability-unaware) score for one pair of color NAMES,
    plus a short tag explaining why. Order of precedence: missing data ->
    rules.py's proven classic pairings -> neutral combinations -> hue-wheel
    relationships -> "uncertain" for anything outside the known palette."""
    if not color_a or not color_b:
        return 0.5, "unknown color"

    a, b = color_a.strip().lower(), color_b.strip().lower()
    pair = frozenset({a, b})

    if pair in rules.HIGH_COLOR_PAIRS:
        return rules.HIGH_COLOR_PAIRS[pair], "classic pairing"
    if pair in rules.GOOD_COLOR_PAIRS:
        return rules.GOOD_COLOR_PAIRS[pair], "classic pairing"

    a_neutral, b_neutral = is_neutral(a), is_neutral(b)
    if a_neutral and b_neutral:
        return 0.85, "neutral combination"
    if a_neutral or b_neutral:
        return 0.80, "neutral pairing"

    relationship = hue_relationship(a, b)
    if relationship == "monochromatic":
        return MONOCHROMATIC_SCORE, "monochromatic"
    if relationship == "complementary":
        return COMPLEMENTARY_SCORE, "complementary colors"
    if relationship == "analogous":
        return ANALOGOUS_SCORE, "analogous colors"
    if relationship == "contrasting":
        return CONTRASTING_SCORE, "contrasting colors"

    # Neither color is in VISTIQ's 14-color palette at all (e.g. free-text
    # manual entry) — genuinely uncertain, same spirit as the original
    # Phase 1 rules.color_pair_score's "no explicit rule" case.
    return UNKNOWN_COLOR_SCORE, "uncertain"


def _reliability_blend_factor(item: ClothingItem) -> float:
    return RELIABILITY_BLEND.get(item.color_reliability, 0.0)


def color_pair_compatibility(item_a: ClothingItem, item_b: ClothingItem) -> tuple[float, str]:
    """Full Phase 3 color compatibility for one pair of garments: primary
    colors, secondary colors (when actually stored), and reliability-aware
    down-weighting — combined into one (score, explanation_tag).

    Secondary colors: if either item has a real, stored `secondary_color`,
    every cross-pairing involving it is also checked, and the BEST one is
    blended in at 30% weight (primary-vs-primary stays the dominant 70%).
    This rewards outfits where a genuinely multi-colored garment's
    secondary shade also harmonizes, without requiring every garment to
    have a secondary color — most won't (see
    app/database/models.py — secondary_color is nullable and, before
    Phase 3, was never actually populated by the frontend at all).

    Reliability: the pair uses whichever of the two items' reliabilities is
    MORE cautious — one unreliable color is enough to make the whole
    pair's reading uncertain. See RELIABILITY_BLEND above for exactly how
    "high"/"medium"/"low"/unknown are weighted.
    """
    primary_score, tag = base_color_pair_score(item_a.color, item_b.color)

    secondary_candidates: list[tuple[float, str]] = []
    if item_a.secondary_color:
        secondary_candidates.append(base_color_pair_score(item_a.secondary_color, item_b.color))
    if item_b.secondary_color:
        secondary_candidates.append(base_color_pair_score(item_a.color, item_b.secondary_color))
    if item_a.secondary_color and item_b.secondary_color:
        secondary_candidates.append(base_color_pair_score(item_a.secondary_color, item_b.secondary_color))

    if secondary_candidates:
        best_secondary_score, best_secondary_tag = max(secondary_candidates, key=lambda candidate: candidate[0])
        combined_score = primary_score * 0.7 + best_secondary_score * 0.3
        if best_secondary_score > primary_score:
            tag = best_secondary_tag
    else:
        combined_score = primary_score

    blend = max(_reliability_blend_factor(item_a), _reliability_blend_factor(item_b))
    if blend > 0.0:
        combined_score = combined_score * (1.0 - blend) + 0.5 * blend
        if blend >= RELIABILITY_BLEND["low"]:
            tag = "uncertain (low color reliability)"

    return round(combined_score, 4), tag
