"""Tests for app/recommendation/personalization.py (Phase 3). No accounts,
no persisted preferences — every test constructs its own
RecommendationRequest with the preference fields set directly."""

from app.recommendation.personalization import personalization_adjustment
from app.schemas.recommendation import RecommendationRequest
from tests.conftest import make_item


def _request(**overrides) -> RecommendationRequest:
    defaults = dict(occasion="Casual")
    defaults.update(overrides)
    return RecommendationRequest(**defaults)


def test_no_preferences_means_zero_adjustment(db_session):
    items = [make_item(db_session, color="Red"), make_item(db_session, color="Blue")]
    adjustment, reasons = personalization_adjustment(items, _request())
    assert adjustment == 0.0
    assert reasons == []


def test_preferred_color_present_gives_a_bonus(db_session):
    items = [make_item(db_session, color="Red"), make_item(db_session, color="Blue")]
    adjustment, reasons = personalization_adjustment(items, _request(preferred_colors=["Red"]))
    assert adjustment > 0
    assert any("prefer" in reason.lower() for reason in reasons)


def test_preferred_color_absent_gives_no_bonus(db_session):
    items = [make_item(db_session, color="Red"), make_item(db_session, color="Blue")]
    adjustment, reasons = personalization_adjustment(items, _request(preferred_colors=["Green"]))
    assert adjustment == 0.0
    assert reasons == []


def test_preferred_color_matches_secondary_color_too(db_session):
    items = [make_item(db_session, color="Red", secondary_color="Green")]
    adjustment, _reasons = personalization_adjustment(items, _request(preferred_colors=["Green"]))
    assert adjustment > 0


def test_avoided_color_present_gives_a_penalty(db_session):
    items = [make_item(db_session, color="Pink"), make_item(db_session, color="Blue")]
    adjustment, reasons = personalization_adjustment(items, _request(avoided_colors=["Pink"]))
    assert adjustment < 0
    assert any("avoid" in reason.lower() for reason in reasons)


def test_preferred_and_avoided_can_both_apply(db_session):
    """An outfit can simultaneously include a preferred color on one item
    and an avoided color on another — both effects should apply."""
    items = [make_item(db_session, color="Red"), make_item(db_session, color="Pink")]
    adjustment, reasons = personalization_adjustment(
        items, _request(preferred_colors=["Red"], avoided_colors=["Pink"])
    )
    assert len(reasons) == 2
    # Penalty (4/item) outweighs bonus (2/item) by design — avoiding a
    # disliked color matters more than including a liked one.
    assert adjustment < 0


def test_favorite_item_preference_gives_a_bonus_when_enabled(db_session):
    items = [make_item(db_session, is_favorite=True), make_item(db_session, is_favorite=False)]
    adjustment, reasons = personalization_adjustment(items, _request(prefer_favorites=True))
    assert adjustment > 0
    assert any("favorite" in reason.lower() for reason in reasons)


def test_favorite_items_ignored_when_preference_disabled(db_session):
    items = [make_item(db_session, is_favorite=True)]
    adjustment, reasons = personalization_adjustment(items, _request(prefer_favorites=False))
    assert adjustment == 0.0
    assert reasons == []


def test_bonus_is_capped_regardless_of_how_many_items_match(db_session):
    items = [make_item(db_session, color="Red") for _ in range(10)]
    adjustment, _reasons = personalization_adjustment(items, _request(preferred_colors=["Red"]))
    from app.recommendation.personalization import MAX_PREFERRED_COLOR_BONUS

    assert adjustment == MAX_PREFERRED_COLOR_BONUS


def test_invalid_or_garbage_preference_value_does_not_crash(db_session):
    items = [make_item(db_session, color="Red")]
    adjustment, reasons = personalization_adjustment(
        items, _request(preferred_colors=["", "   ", "not-a-real-color-at-all"])
    )
    assert adjustment == 0.0
    assert reasons == []


def test_empty_items_list_does_not_crash(db_session):
    adjustment, reasons = personalization_adjustment([], _request(preferred_colors=["Red"], prefer_favorites=True))
    assert adjustment == 0.0
    assert reasons == []
