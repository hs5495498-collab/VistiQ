"""
Pure, deterministic compatibility rules for the VISTIQ recommendation engine.

Every function here takes plain strings (never a database session, never a
FastAPI object) and returns a score between 0.0 and 1.0. Keeping this module
free of side effects makes it easy to test and to explain in a viva: the same
input always produces the same output.
"""

# ---------------------------------------------------------------------------
# Category compatibility
# ---------------------------------------------------------------------------

KNOWN_CATEGORIES = ["Tops", "Bottoms", "Outerwear", "Dresses", "Footwear", "Accessories"]

CATEGORY_COMPATIBILITY: dict[str, set[str]] = {
    "Tops": {"Bottoms", "Outerwear", "Footwear", "Accessories"},
    "Bottoms": {"Tops", "Outerwear", "Footwear", "Accessories"},
    "Outerwear": {"Tops", "Bottoms", "Footwear", "Accessories"},
    "Dresses": {"Footwear", "Outerwear", "Accessories"},
    "Footwear": {"Tops", "Bottoms", "Dresses", "Outerwear", "Accessories"},
    "Accessories": {"Tops", "Bottoms", "Dresses", "Outerwear", "Footwear"},
}


def normalize_category(category: str | None) -> str | None:
    """Map a free-text category string to one of KNOWN_CATEGORIES, or None."""
    if not category:
        return None
    lowered = category.strip().lower()
    for known in KNOWN_CATEGORIES:
        if known.lower() == lowered:
            return known
    return None


def category_pair_score(category_a: str | None, category_b: str | None) -> float:
    """1.0 for a complementary pair (e.g. Tops+Bottoms), 0.0 otherwise —
    including the same category twice (e.g. Tops+Tops is redundant)."""
    a = normalize_category(category_a)
    b = normalize_category(category_b)
    if a is None or b is None or a == b:
        return 0.0
    return 1.0 if b in CATEGORY_COMPATIBILITY.get(a, set()) else 0.0


# ---------------------------------------------------------------------------
# Color compatibility
# ---------------------------------------------------------------------------

NEUTRAL_COLORS = {
    "black", "white", "grey", "gray", "beige", "navy",
    "indigo", "brown", "cream", "tan", "charcoal", "ivory",
}

# Classic, broadly-agreed high-harmony pairings.
HIGH_COLOR_PAIRS: dict[frozenset[str], float] = {
    frozenset({"black", "white"}): 0.95,
    frozenset({"navy", "white"}): 0.95,
    frozenset({"beige", "brown"}): 0.9,
    frozenset({"grey", "black"}): 0.9,
    frozenset({"gray", "black"}): 0.9,
    frozenset({"indigo", "white"}): 0.9,
    frozenset({"navy", "beige"}): 0.85,
    frozenset({"black", "beige"}): 0.85,
    frozenset({"white", "brown"}): 0.85,
    frozenset({"indigo", "beige"}): 0.8,
}

# Good but slightly less classic pairings.
GOOD_COLOR_PAIRS: dict[frozenset[str], float] = {
    frozenset({"green", "beige"}): 0.8,
    frozenset({"green", "white"}): 0.75,
    frozenset({"green", "navy"}): 0.7,
    frozenset({"red", "black"}): 0.75,
    frozenset({"red", "white"}): 0.7,
    frozenset({"blue", "white"}): 0.75,
    frozenset({"blue", "beige"}): 0.7,
    frozenset({"indigo", "grey"}): 0.75,
    frozenset({"indigo", "gray"}): 0.75,
}


def color_pair_score(color_a: str | None, color_b: str | None) -> float:
    """Outfit color harmony, not duplicate-color matching — an exact repeat
    scores decently (monochrome can look good) but never as high as a real
    complementary neutral pairing."""
    if not color_a or not color_b:
        return 0.5

    a, b = color_a.strip().lower(), color_b.strip().lower()
    pair = frozenset({a, b})

    if pair in HIGH_COLOR_PAIRS:
        return HIGH_COLOR_PAIRS[pair]
    if pair in GOOD_COLOR_PAIRS:
        return GOOD_COLOR_PAIRS[pair]
    if a == b:
        return 0.7

    a_neutral, b_neutral = a in NEUTRAL_COLORS, b in NEUTRAL_COLORS
    if a_neutral and b_neutral:
        return 0.85
    if a_neutral or b_neutral:
        return 0.75

    # Two different, non-neutral colors with no explicit rule: uncertain.
    return 0.45


# ---------------------------------------------------------------------------
# Style compatibility
# ---------------------------------------------------------------------------

STYLE_ALIASES = {
    "minimalist": "minimal",
    "minimal": "minimal",
    "streetwear": "streetwear",
    "smart casual": "smart casual",
    "casual": "casual",
    "formal": "formal",
    "sporty": "sporty",
}

STYLE_COMPATIBILITY_PAIRS: dict[frozenset[str], float] = {
    frozenset({"streetwear", "minimal"}): 0.6,
    frozenset({"smart casual", "minimal"}): 0.65,
    frozenset({"smart casual", "streetwear"}): 0.4,
    frozenset({"casual", "streetwear"}): 0.75,
    frozenset({"casual", "smart casual"}): 0.65,
    frozenset({"casual", "minimal"}): 0.7,
    frozenset({"casual", "formal"}): 0.3,
    frozenset({"formal", "streetwear"}): 0.2,
    frozenset({"formal", "smart casual"}): 0.75,
    frozenset({"formal", "minimal"}): 0.6,
    frozenset({"sporty", "formal"}): 0.2,
    frozenset({"sporty", "streetwear"}): 0.6,
    frozenset({"sporty", "casual"}): 0.7,
    frozenset({"sporty", "minimal"}): 0.45,
    frozenset({"sporty", "smart casual"}): 0.35,
}

DEFAULT_STYLE_SCORE = 0.5


def normalize_style(style: str) -> str:
    lowered = style.strip().lower()
    return STYLE_ALIASES.get(lowered, lowered)


def style_pair_score(style_a: str | None, style_b: str | None) -> float:
    if not style_a or not style_b:
        return DEFAULT_STYLE_SCORE
    a, b = normalize_style(style_a), normalize_style(style_b)
    if a == b:
        return 1.0
    return STYLE_COMPATIBILITY_PAIRS.get(frozenset({a, b}), DEFAULT_STYLE_SCORE)


# ---------------------------------------------------------------------------
# Occasion compatibility
# ---------------------------------------------------------------------------

OCCASION_ALIASES = {
    "work": "work",
    "studio": "work",
    "work / studio": "work",
    "office": "work",
    "casual": "casual",
    "college": "casual",
    "night out": "night out",
    "party": "night out",
    "date": "night out",
    "formal": "formal",
}

DEFAULT_OCCASION_SCORE = 0.5
OCCASION_MISMATCH_SCORE = 0.35


def normalize_occasion(occasion: str) -> str:
    lowered = occasion.strip().lower()
    return OCCASION_ALIASES.get(lowered, lowered)


def occasion_match_score(item_occasion: str | None, requested_occasion: str | None) -> float:
    """Item occasion is a free-text field that may list several occasions
    separated by commas (e.g. "Casual, College")."""
    if not requested_occasion:
        return DEFAULT_OCCASION_SCORE
    if not item_occasion:
        return DEFAULT_OCCASION_SCORE

    requested = normalize_occasion(requested_occasion)
    item_occasions = [normalize_occasion(o) for o in item_occasion.split(",") if o.strip()]
    return 1.0 if requested in item_occasions else OCCASION_MISMATCH_SCORE


# ---------------------------------------------------------------------------
# Weather / season compatibility
# ---------------------------------------------------------------------------

WEATHER_TO_SEASON: dict[str, set[str]] = {
    "warm": {"warm weather", "all season"},
    "cool": {"cool weather", "layering pieces", "all season"},
    "cold": {"layering pieces", "cool weather"},
    "rainy": {"layering pieces", "all season"},
}

DEFAULT_WEATHER_SCORE = 0.5
WEATHER_MISMATCH_SCORE = 0.3
WEATHER_MATCH_SCORE = 0.95
RAIN_OUTERWEAR_BONUS = 0.1


def weather_match_score(
    item_season: str | None,
    requested_weather: str | None,
    item_category: str | None = None,
) -> float:
    if not requested_weather:
        return DEFAULT_WEATHER_SCORE

    weather_key = requested_weather.strip().lower()
    matching_seasons = WEATHER_TO_SEASON.get(weather_key)
    if matching_seasons is None:
        return DEFAULT_WEATHER_SCORE

    if not item_season:
        return DEFAULT_WEATHER_SCORE

    season_key = item_season.strip().lower()
    score = WEATHER_MATCH_SCORE if season_key in matching_seasons else WEATHER_MISMATCH_SCORE

    # Rain calls for outerwear/footwear regardless of season tag.
    normalized_category = normalize_category(item_category)
    if weather_key == "rainy" and normalized_category in {"Outerwear", "Footwear"}:
        score = min(1.0, score + RAIN_OUTERWEAR_BONUS)

    return score
