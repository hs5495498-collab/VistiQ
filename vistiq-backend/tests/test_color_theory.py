"""Tests for app/recommendation/color_theory.py (Phase 3). K-means is
never involved here — this module is pure, deterministic color-theory math
over VISTIQ's existing 14-color named palette, plus reliability-aware
down-weighting of stored per-item color_reliability."""

from app.recommendation import color_theory as ct
from tests.conftest import make_item


# --- Hue computation / neutral classification --------------------------------


def test_classic_neutrals_are_neutral():
    for name in ("black", "white", "grey", "navy", "beige", "brown", "indigo"):
        assert ct.is_neutral(name) is True


def test_chromatic_colors_are_not_neutral():
    for name in ("red", "blue", "green", "yellow", "pink", "purple", "orange"):
        assert ct.is_neutral(name) is False


def test_hue_table_covers_every_palette_color():
    from ml.training.config import COLOR_PALETTE

    assert set(ct._HUE_BY_NAME.keys()) == {name.lower() for name in COLOR_PALETTE}


# --- Hue-wheel relationships ---------------------------------------------------


def test_same_chromatic_color_is_monochromatic():
    assert ct.hue_relationship("red", "red") == "monochromatic"


def test_blue_and_yellow_are_complementary():
    # Verified empirically: hues ~218 and ~48 degrees apart ~170 degrees —
    # squarely in the complementary band.
    assert ct.hue_relationship("blue", "yellow") == "complementary"


def test_orange_and_yellow_are_analogous():
    assert ct.hue_relationship("orange", "yellow") == "analogous"


def test_blue_and_red_are_contrasting_not_complementary():
    # Verified empirically: ~142 degrees apart — outside both the
    # complementary (150-210) and analogous (<=40) bands.
    assert ct.hue_relationship("blue", "red") == "contrasting"


def test_hue_relationship_is_none_for_neutral_colors():
    assert ct.hue_relationship("black", "red") is None
    assert ct.hue_relationship("white", "black") is None


def test_hue_relationship_is_none_for_unknown_color_names():
    assert ct.hue_relationship("red", "not-a-real-color") is None


# --- base_color_pair_score: precedence and fallback ---------------------------


def test_classic_pair_table_takes_precedence_over_hue_math():
    # black+white is in rules.HIGH_COLOR_PAIRS (0.95) — must win even
    # though black/white's hue relationship is meaningless (see
    # color_theory.py's documented colorsys edge case).
    score, tag = ct.base_color_pair_score("black", "white")
    assert score == 0.95
    assert tag == "classic pairing"


def test_neutral_combination_not_in_classic_table():
    score, tag = ct.base_color_pair_score("grey", "brown")
    assert tag == "neutral combination"
    assert score == 0.85


def test_neutral_plus_chromatic_pairing():
    score, tag = ct.base_color_pair_score("black", "green")
    assert tag == "neutral pairing"
    assert score == 0.80


def test_missing_color_is_unknown_not_a_crash():
    score, tag = ct.base_color_pair_score(None, "red")
    assert score == 0.5
    assert tag == "unknown color"
    score, tag = ct.base_color_pair_score("", "red")
    assert score == 0.5


def test_unknown_color_name_outside_palette_is_uncertain_not_a_crash():
    score, tag = ct.base_color_pair_score("red", "chartreuse")
    assert tag == "uncertain"
    assert 0.0 <= score <= 1.0


def test_score_is_case_and_whitespace_insensitive():
    a = ct.base_color_pair_score("Black", "White")
    b = ct.base_color_pair_score(" black ", " WHITE ")
    assert a == b


# --- color_pair_compatibility: secondary colors + reliability -----------------


def test_secondary_color_is_considered_when_present(db_session):
    # Primary colors clash (orange/blue-ish contrasting), but item_a's
    # secondary color is a classic pairing with item_b's primary — the
    # combined score must reflect that, not just the primary-only score.
    item_a = make_item(db_session, color="Orange", secondary_color="White")
    item_b = make_item(db_session, color="Navy")

    combined_score, _tag = ct.color_pair_compatibility(item_a, item_b)
    primary_only_score, _ = ct.base_color_pair_score("Orange", "Navy")

    assert combined_score != primary_only_score


def test_no_secondary_color_falls_back_to_primary_only(db_session):
    item_a = make_item(db_session, color="Black", secondary_color=None)
    item_b = make_item(db_session, color="White", secondary_color=None)

    combined_score, tag = ct.color_pair_compatibility(item_a, item_b)
    primary_score, primary_tag = ct.base_color_pair_score("Black", "White")

    assert combined_score == primary_score
    assert tag == primary_tag


def test_high_reliability_is_not_down_weighted(db_session):
    item_a = make_item(db_session, color="Black", color_reliability="high")
    item_b = make_item(db_session, color="White", color_reliability="high")

    score, _tag = ct.color_pair_compatibility(item_a, item_b)
    assert score == 0.95  # unmodified classic-pair score


def test_unknown_reliability_none_is_not_penalized(db_session):
    """Explicit regression test for the approved design decision: an item
    created before this column existed (color_reliability=None) must be
    treated exactly like 'high', never like 'low'."""
    item_a = make_item(db_session, color="Black", color_reliability=None)
    item_b = make_item(db_session, color="White", color_reliability=None)

    score, _tag = ct.color_pair_compatibility(item_a, item_b)
    assert score == 0.95


def test_low_reliability_pulls_score_toward_neutral(db_session):
    item_a = make_item(db_session, color="Black", color_reliability="low")
    item_b = make_item(db_session, color="White", color_reliability="high")

    score, tag = ct.color_pair_compatibility(item_a, item_b)
    assert score < 0.95  # pulled down from the full classic-pair score
    assert score > 0.5  # but not fully discarded either
    assert "uncertain" in tag.lower()


def test_medium_reliability_partially_down_weights(db_session):
    item_a = make_item(db_session, color="Black", color_reliability="medium")
    item_b = make_item(db_session, color="White", color_reliability="high")

    medium_score, _ = ct.color_pair_compatibility(item_a, item_b)

    item_a.color_reliability = "low"
    low_score, _ = ct.color_pair_compatibility(item_a, item_b)

    # Medium discounts less than low — score should sit strictly between
    # the full-trust score and the low-trust score.
    assert low_score < medium_score < 0.95


def test_pair_reliability_uses_the_more_cautious_item(db_session):
    """One low-reliability item is enough to make the WHOLE pair's color
    reading uncertain, even if the other item is high-reliability."""
    both_high = ct.color_pair_compatibility(
        make_item(db_session, color="Black", color_reliability="high"),
        make_item(db_session, color="White", color_reliability="high"),
    )
    one_low = ct.color_pair_compatibility(
        make_item(db_session, color="Black", color_reliability="high"),
        make_item(db_session, color="White", color_reliability="low"),
    )
    assert one_low[0] < both_high[0]


def test_color_pair_compatibility_is_deterministic(db_session):
    item_a = make_item(db_session, color="Blue", secondary_color="Beige")
    item_b = make_item(db_session, color="Orange", color_reliability="medium")

    first = ct.color_pair_compatibility(item_a, item_b)
    second = ct.color_pair_compatibility(item_a, item_b)
    assert first == second
