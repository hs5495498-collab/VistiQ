"""
Per-item and per-outfit scoring built on top of the pure rules in rules.py
and (Phase 3) the color-theory module in color_theory.py.

score_outfit() is the single place the six weighted dimensions come
together into one final 0-100 score. Nothing here is random and nothing is
hard-coded — every score is computed from the actual items and request.
"""

import itertools

from app.database.models import ClothingItem
from app.recommendation import color_theory, rules

# Weights must sum to 1.0.
WEIGHT_COLOR = 0.30
WEIGHT_CATEGORY = 0.20
WEIGHT_STYLE = 0.20
WEIGHT_OCCASION = 0.15
WEIGHT_PREFERENCE = 0.10
WEIGHT_WEATHER = 0.05

WEAR_COUNT_CAP = 10  # wear_count at/above this gets the full preference score


def calculate_color_compatibility(item_a: ClothingItem, item_b: ClothingItem) -> tuple[float, str]:
    """Phase 3: real color-theory compatibility (hue relationships +
    secondary colors + reliability-aware down-weighting), not just the
    classic-pairs-or-default lookup. See color_theory.py. rules.py's
    original color_pair_score() is left completely untouched — it's still
    directly unit-tested in tests/test_recommendation_rules.py — this is
    the one call site that now points at the richer function instead."""
    return color_theory.color_pair_compatibility(item_a, item_b)


def calculate_category_compatibility(item_a: ClothingItem, item_b: ClothingItem) -> float:
    return rules.category_pair_score(item_a.category, item_b.category)


def calculate_style_compatibility(item_a: ClothingItem, item_b: ClothingItem) -> float:
    return rules.style_pair_score(item_a.style, item_b.style)


def calculate_occasion_compatibility(item: ClothingItem, requested_occasion: str | None) -> float:
    return rules.occasion_match_score(item.occasion, requested_occasion)


def calculate_weather_compatibility(item: ClothingItem, requested_weather: str | None) -> float:
    return rules.weather_match_score(item.season, requested_weather, item.category)


def calculate_preference_score(item: ClothingItem) -> float:
    """Small wear-history boost — capped so it can never dominate the score."""
    wear_count = item.wear_count or 0
    return min(wear_count / WEAR_COUNT_CAP, 1.0)


def score_outfit(
    items: list[ClothingItem],
    occasion: str,
    style: str | None,
    weather: str | None,
) -> tuple[float, dict[str, float], dict]:
    """Score one candidate outfit.

    Returns (final_score_0_100, breakdown_0_1, evidence) — `evidence` is
    Phase 3's addition: the concrete, non-fabricated facts behind the
    scores (which color relationships were actually found, whether any
    item's color reliability was low), used by
    app/recommendation/engine.py to build a structured, honest explanation
    instead of a generic one. Nothing here is random and nothing is
    hard-coded — every score and every piece of evidence is computed from
    the actual items and request.
    """
    pairs = list(itertools.combinations(items, 2))

    color_tags: list[str] = []
    if pairs:
        color_results = [calculate_color_compatibility(a, b) for a, b in pairs]
        color_score = sum(score for score, _tag in color_results) / len(color_results)
        color_tags = [tag for _score, tag in color_results]
        category_score = sum(calculate_category_compatibility(a, b) for a, b in pairs) / len(pairs)
        style_score = sum(calculate_style_compatibility(a, b) for a, b in pairs) / len(pairs)
    else:
        # A single-item "outfit" (e.g. a standalone dress) has nothing to pair — neutral.
        color_score = category_score = style_score = 0.5

    # Also weigh each item's style against the explicitly requested style, if any.
    if style:
        style_vs_request = sum(rules.style_pair_score(i.style, style) for i in items) / len(items)
        style_score = (style_score + style_vs_request) / 2

    occasion_score = sum(calculate_occasion_compatibility(i, occasion) for i in items) / len(items)
    weather_score = sum(calculate_weather_compatibility(i, weather) for i in items) / len(items)
    preference_score = sum(calculate_preference_score(i) for i in items) / len(items)

    weighted = (
        color_score * WEIGHT_COLOR
        + category_score * WEIGHT_CATEGORY
        + style_score * WEIGHT_STYLE
        + occasion_score * WEIGHT_OCCASION
        + preference_score * WEIGHT_PREFERENCE
        + weather_score * WEIGHT_WEATHER
    )

    breakdown = {
        "color": color_score,
        "category": category_score,
        "style": style_score,
        "occasion": occasion_score,
        "weather": weather_score,
        "preference": preference_score,
    }
    evidence = {
        "color_tags": color_tags,
        "low_color_reliability": any("uncertain (low color reliability)" == tag for tag in color_tags),
    }
    return round(weighted * 100, 1), breakdown, evidence
