"""Integration tests for app/recommendation/engine.build_recommendations(),
exercised directly against a real (in-memory) database session — these cover
the full candidate-generation -> scoring -> ranking pipeline, not just the
pure rule functions in test_recommendation_rules.py."""

import pytest
from fastapi import HTTPException

from app.recommendation.engine import build_recommendations
from app.schemas.recommendation import RecommendationRequest
from tests.conftest import make_item


def test_valid_outfit_generation_returns_complete_outfit(db_session):
    top = make_item(db_session, name="Black Shirt", category="Tops", color="Black", style="Formal")
    bottom = make_item(db_session, name="Black Trouser", category="Bottoms", color="Black", style="Formal")
    shoes = make_item(db_session, name="Brown Shoes", category="Footwear", color="Brown", style="Formal")

    request = RecommendationRequest(
        occasion="Office",
        wardrobe_item_ids=[top.id, bottom.id, shoes.id],
        top_k=3,
    )
    result = build_recommendations(db_session, request)

    assert result["message"] is None
    assert len(result["recommendations"]) >= 1
    top_outfit = result["recommendations"][0]
    outfit_item_ids = {item["id"] for item in top_outfit["items"]}
    # A full Tops+Bottoms+Footwear outfit should be preferred over any
    # partial template when all three categories are available.
    assert outfit_item_ids == {top.id, bottom.id, shoes.id}


def test_color_compatibility_scoring_prefers_classic_pairing(db_session):
    """Two otherwise-identical outfits, differing only in color harmony —
    the classic black+white pairing must score higher than an arbitrary,
    unlisted color pairing."""
    good_top = make_item(db_session, name="White Shirt", category="Tops", color="White", style="Formal")
    bad_top = make_item(db_session, name="Orange Shirt", category="Tops", color="Orange", style="Formal")
    bottom = make_item(db_session, name="Black Trouser", category="Bottoms", color="Black", style="Formal")

    request = RecommendationRequest(
        occasion="Office",
        wardrobe_item_ids=[good_top.id, bad_top.id, bottom.id],
        top_k=10,
    )
    result = build_recommendations(db_session, request)

    scores_by_top_id = {}
    for rec in result["recommendations"]:
        for item in rec["items"]:
            if item["id"] in (good_top.id, bad_top.id):
                scores_by_top_id[item["id"]] = rec["score"]

    assert scores_by_top_id[good_top.id] > scores_by_top_id[bad_top.id]


def test_category_compatibility_rejects_duplicate_category_pairing(db_session):
    """A Tops+Tops outfit should never be generated — Tops is not in its
    own CATEGORY_COMPATIBILITY set, so no template matches two tops alone."""
    top_a = make_item(db_session, name="Shirt A", category="Tops", color="Black", style="Casual")
    top_b = make_item(db_session, name="Shirt B", category="Tops", color="White", style="Casual")

    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[top_a.id, top_b.id], top_k=5)
    result = build_recommendations(db_session, request)

    assert result["recommendations"] == []
    assert "Not enough variety" in result["message"]


def test_style_matching_influences_ranking(db_session):
    formal_top = make_item(db_session, name="Blazer", category="Tops", color="Navy", style="Formal")
    casual_top = make_item(db_session, name="Tee", category="Tops", color="Navy", style="Casual")
    formal_bottom = make_item(db_session, name="Slacks", category="Bottoms", color="Navy", style="Formal")

    request = RecommendationRequest(
        occasion="Office",
        style="Formal",
        wardrobe_item_ids=[formal_top.id, casual_top.id, formal_bottom.id],
        top_k=10,
    )
    result = build_recommendations(db_session, request)

    scores_by_top_id = {}
    for rec in result["recommendations"]:
        for item in rec["items"]:
            if item["id"] in (formal_top.id, casual_top.id):
                scores_by_top_id[item["id"]] = rec["score"]

    assert scores_by_top_id[formal_top.id] > scores_by_top_id[casual_top.id]


def test_occasion_matching_influences_ranking(db_session):
    office_top = make_item(db_session, name="Office Shirt", category="Tops", color="Black", style="Casual", occasion="Office")
    party_top = make_item(db_session, name="Party Shirt", category="Tops", color="Black", style="Casual", occasion="Party")
    bottom = make_item(db_session, name="Trouser", category="Bottoms", color="Black", style="Casual", occasion="Office, Party")

    request = RecommendationRequest(
        occasion="Office",
        wardrobe_item_ids=[office_top.id, party_top.id, bottom.id],
        top_k=10,
    )
    result = build_recommendations(db_session, request)

    scores_by_top_id = {}
    for rec in result["recommendations"]:
        for item in rec["items"]:
            if item["id"] in (office_top.id, party_top.id):
                scores_by_top_id[item["id"]] = rec["score"]

    assert scores_by_top_id[office_top.id] > scores_by_top_id[party_top.id]


def test_weather_and_season_compatibility_influences_ranking(db_session):
    warm_top = make_item(db_session, name="Linen Shirt", category="Tops", color="Beige", style="Casual", season="Warm Weather")
    cold_top = make_item(db_session, name="Wool Sweater", category="Tops", color="Beige", style="Casual", season="Cool Weather")
    bottom = make_item(db_session, name="Chinos", category="Bottoms", color="Beige", style="Casual", season="All Season")

    request = RecommendationRequest(
        occasion="Casual",
        weather="Warm",
        wardrobe_item_ids=[warm_top.id, cold_top.id, bottom.id],
        top_k=10,
    )
    result = build_recommendations(db_session, request)

    scores_by_top_id = {}
    for rec in result["recommendations"]:
        for item in rec["items"]:
            if item["id"] in (warm_top.id, cold_top.id):
                scores_by_top_id[item["id"]] = rec["score"]

    assert scores_by_top_id[warm_top.id] > scores_by_top_id[cold_top.id]


def test_anchor_item_is_present_in_every_recommendation(db_session):
    anchor_shoes = make_item(db_session, name="Red Sneakers", category="Footwear", color="Red", style="Streetwear")
    other_shoes = make_item(db_session, name="Black Boots", category="Footwear", color="Black", style="Formal")
    top = make_item(db_session, name="Hoodie", category="Tops", color="Grey", style="Streetwear")
    bottom = make_item(db_session, name="Joggers", category="Bottoms", color="Grey", style="Streetwear")

    request = RecommendationRequest(
        occasion="Casual",
        wardrobe_item_ids=[other_shoes.id, top.id, bottom.id],
        selected_item_id=anchor_shoes.id,
        top_k=10,
    )
    result = build_recommendations(db_session, request)

    assert len(result["recommendations"]) >= 1
    for rec in result["recommendations"]:
        item_ids = {item["id"] for item in rec["items"]}
        assert anchor_shoes.id in item_ids


def test_anchor_item_not_found_raises_404(db_session):
    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[], selected_item_id=999999)
    with pytest.raises(HTTPException) as exc_info:
        build_recommendations(db_session, request)
    assert exc_info.value.status_code == 404


def test_deterministic_ranking_same_input_same_output(db_session):
    top = make_item(db_session, name="Shirt", category="Tops", color="Black", style="Formal")
    bottom = make_item(db_session, name="Trouser", category="Bottoms", color="Black", style="Formal")
    shoes = make_item(db_session, name="Shoes", category="Footwear", color="Black", style="Formal")
    accessory = make_item(db_session, name="Belt", category="Accessories", color="Black", style="Formal")

    request = RecommendationRequest(
        occasion="Office",
        wardrobe_item_ids=[top.id, bottom.id, shoes.id, accessory.id],
        top_k=10,
    )

    first = build_recommendations(db_session, request)
    second = build_recommendations(db_session, request)

    assert first["recommendations"] == second["recommendations"]


def test_empty_wardrobe_pool_returns_empty_recommendations_with_message(db_session):
    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[])
    result = build_recommendations(db_session, request)

    assert result["recommendations"] == []
    assert result["message"] is not None
    assert "empty" in result["message"].lower()


def test_nonexistent_wardrobe_ids_returns_empty_with_message(db_session):
    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[12345, 67890])
    result = build_recommendations(db_session, request)

    assert result["recommendations"] == []
    assert result["message"] is not None


def test_insufficient_wardrobe_single_category_returns_no_recommendations(db_session):
    """A lone Accessories item can't satisfy any outfit template on its
    own — no template's required categories are a subset of {Accessories}."""
    accessory = make_item(db_session, name="Watch", category="Accessories", color="Black", style="Formal")

    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[accessory.id])
    result = build_recommendations(db_session, request)

    assert result["recommendations"] == []
    assert "Not enough variety" in result["message"]


def test_partial_outfit_used_when_no_full_template_available(db_session):
    """Tops + Bottoms with no Footwear in the pool should still produce a
    partial outfit, with the explanation noting what's missing."""
    top = make_item(db_session, name="Shirt", category="Tops", color="Black", style="Casual")
    bottom = make_item(db_session, name="Jeans", category="Bottoms", color="Black", style="Casual")

    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[top.id, bottom.id])
    result = build_recommendations(db_session, request)

    assert len(result["recommendations"]) >= 1
    assert "partial outfit" in result["recommendations"][0]["reason"]
