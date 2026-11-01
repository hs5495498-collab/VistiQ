"""Unit tests for app/recommendation/rules.py and scoring.py — pure
functions, no database, no FastAPI. These pin down the compatibility rules
the recommendation engine is built on."""

from app.recommendation import rules
from app.recommendation.scoring import (
    WEIGHT_CATEGORY,
    WEIGHT_COLOR,
    WEIGHT_OCCASION,
    WEIGHT_PREFERENCE,
    WEIGHT_STYLE,
    WEIGHT_WEATHER,
)


def test_scoring_weights_sum_to_one():
    total = (
        WEIGHT_COLOR + WEIGHT_CATEGORY + WEIGHT_STYLE + WEIGHT_OCCASION + WEIGHT_PREFERENCE + WEIGHT_WEATHER
    )
    assert total == 1.0


# --- Category compatibility --------------------------------------------------


def test_category_pair_score_complementary():
    assert rules.category_pair_score("Tops", "Bottoms") == 1.0


def test_category_pair_score_same_category_is_zero():
    assert rules.category_pair_score("Tops", "Tops") == 0.0


def test_category_pair_score_unknown_category_is_zero():
    assert rules.category_pair_score("Tops", "NotARealCategory") == 0.0


def test_normalize_category_is_case_insensitive():
    assert rules.normalize_category("tops") == "Tops"
    assert rules.normalize_category("  Bottoms ") == "Bottoms"
    assert rules.normalize_category(None) is None


# --- Color compatibility -----------------------------------------------------


def test_color_pair_score_classic_high_pair():
    assert rules.color_pair_score("Black", "White") == 0.95


def test_color_pair_score_is_case_insensitive_and_order_independent():
    assert rules.color_pair_score("white", "BLACK") == rules.color_pair_score("Black", "White")


def test_color_pair_score_same_color_is_decent_but_not_top():
    score = rules.color_pair_score("Red", "Red")
    assert 0.0 < score < 0.95


def test_color_pair_score_missing_color_is_neutral():
    assert rules.color_pair_score(None, "Black") == 0.5


def test_color_pair_score_two_neutrals_scores_well():
    assert rules.color_pair_score("Grey", "Beige") >= 0.85


# --- Style compatibility ------------------------------------------------------


def test_style_pair_score_same_style_is_perfect():
    assert rules.style_pair_score("Formal", "Formal") == 1.0


def test_style_pair_score_known_pair():
    assert rules.style_pair_score("Formal", "Streetwear") == 0.2


def test_style_pair_score_unknown_pair_is_default():
    # No explicit rule for this (fabricated) style name -> default score.
    assert rules.style_pair_score("Casual", "SomeUnknownStyle") == 0.5


def test_style_pair_score_missing_style_is_default():
    assert rules.style_pair_score(None, "Casual") == 0.5


# --- Occasion compatibility ---------------------------------------------------


def test_occasion_match_score_exact_match():
    assert rules.occasion_match_score("Office, College", "Office") == 1.0


def test_occasion_match_score_mismatch():
    assert rules.occasion_match_score("Party", "Office") == rules.OCCASION_MISMATCH_SCORE


def test_occasion_match_score_no_requested_occasion_is_default():
    assert rules.occasion_match_score("Office", None) == rules.DEFAULT_OCCASION_SCORE


def test_occasion_match_score_item_has_no_occasion_is_default():
    assert rules.occasion_match_score(None, "Office") == rules.DEFAULT_OCCASION_SCORE


# --- Weather / season compatibility ------------------------------------------


def test_weather_match_score_matching_season():
    assert rules.weather_match_score("Warm Weather", "Warm") == rules.WEATHER_MATCH_SCORE


def test_weather_match_score_mismatched_season():
    assert rules.weather_match_score("Warm Weather", "Cold") == rules.WEATHER_MISMATCH_SCORE


def test_weather_match_score_no_requested_weather_is_default():
    assert rules.weather_match_score("Warm Weather", None) == rules.DEFAULT_WEATHER_SCORE


def test_weather_match_score_rain_outerwear_bonus():
    plain = rules.weather_match_score("Layering Pieces", "Rainy", item_category="Tops")
    bonus = rules.weather_match_score("Layering Pieces", "Rainy", item_category="Outerwear")
    assert bonus > plain
    assert bonus <= 1.0
