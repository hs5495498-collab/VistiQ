"""Integration tests for app/recommendation/engine.build_recommendations(),
exercised directly against a real (in-memory) database session — these cover
the full candidate-generation -> scoring -> ranking pipeline, not just the
pure rule functions in test_recommendation_rules.py."""

import pytest
from fastapi import HTTPException

from app.recommendation.engine import build_recommendations
from app.schemas.recommendation import RecommendationRequest
from tests.conftest import make_item


def test_valid_outfit_generation_returns_complete_outfit(db_session, test_user_id):
    top = make_item(db_session, name="Black Shirt", category="Tops", color="Black", style="Formal")
    bottom = make_item(db_session, name="Black Trouser", category="Bottoms", color="Black", style="Formal")
    shoes = make_item(db_session, name="Brown Shoes", category="Footwear", color="Brown", style="Formal")

    request = RecommendationRequest(
        occasion="Office",
        wardrobe_item_ids=[top.id, bottom.id, shoes.id],
        top_k=3,
    )
    result = build_recommendations(db_session, request, test_user_id)

    assert result["message"] is None
    assert len(result["recommendations"]) >= 1
    top_outfit = result["recommendations"][0]
    outfit_item_ids = {item["id"] for item in top_outfit["items"]}
    # A full Tops+Bottoms+Footwear outfit should be preferred over any
    # partial template when all three categories are available.
    assert outfit_item_ids == {top.id, bottom.id, shoes.id}


def test_color_compatibility_scoring_prefers_classic_pairing(db_session, test_user_id):
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
    result = build_recommendations(db_session, request, test_user_id)

    scores_by_top_id = {}
    for rec in result["recommendations"]:
        for item in rec["items"]:
            if item["id"] in (good_top.id, bad_top.id):
                scores_by_top_id[item["id"]] = rec["score"]

    assert scores_by_top_id[good_top.id] > scores_by_top_id[bad_top.id]


def test_category_compatibility_rejects_duplicate_category_pairing(db_session, test_user_id):
    """A Tops+Tops outfit should never be generated — Tops is not in its
    own CATEGORY_COMPATIBILITY set, so no template matches two tops alone."""
    top_a = make_item(db_session, name="Shirt A", category="Tops", color="Black", style="Casual")
    top_b = make_item(db_session, name="Shirt B", category="Tops", color="White", style="Casual")

    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[top_a.id, top_b.id], top_k=5)
    result = build_recommendations(db_session, request, test_user_id)

    assert result["recommendations"] == []
    assert "Not enough variety" in result["message"]


def test_style_matching_influences_ranking(db_session, test_user_id):
    formal_top = make_item(db_session, name="Blazer", category="Tops", color="Navy", style="Formal")
    casual_top = make_item(db_session, name="Tee", category="Tops", color="Navy", style="Casual")
    formal_bottom = make_item(db_session, name="Slacks", category="Bottoms", color="Navy", style="Formal")

    request = RecommendationRequest(
        occasion="Office",
        style="Formal",
        wardrobe_item_ids=[formal_top.id, casual_top.id, formal_bottom.id],
        top_k=10,
    )
    result = build_recommendations(db_session, request, test_user_id)

    scores_by_top_id = {}
    for rec in result["recommendations"]:
        for item in rec["items"]:
            if item["id"] in (formal_top.id, casual_top.id):
                scores_by_top_id[item["id"]] = rec["score"]

    assert scores_by_top_id[formal_top.id] > scores_by_top_id[casual_top.id]


def test_occasion_matching_influences_ranking(db_session, test_user_id):
    office_top = make_item(db_session, name="Office Shirt", category="Tops", color="Black", style="Casual", occasion="Office")
    party_top = make_item(db_session, name="Party Shirt", category="Tops", color="Black", style="Casual", occasion="Party")
    bottom = make_item(db_session, name="Trouser", category="Bottoms", color="Black", style="Casual", occasion="Office, Party")

    request = RecommendationRequest(
        occasion="Office",
        wardrobe_item_ids=[office_top.id, party_top.id, bottom.id],
        top_k=10,
    )
    result = build_recommendations(db_session, request, test_user_id)

    scores_by_top_id = {}
    for rec in result["recommendations"]:
        for item in rec["items"]:
            if item["id"] in (office_top.id, party_top.id):
                scores_by_top_id[item["id"]] = rec["score"]

    assert scores_by_top_id[office_top.id] > scores_by_top_id[party_top.id]


def test_weather_and_season_compatibility_influences_ranking(db_session, test_user_id):
    warm_top = make_item(db_session, name="Linen Shirt", category="Tops", color="Beige", style="Casual", season="Warm Weather")
    cold_top = make_item(db_session, name="Wool Sweater", category="Tops", color="Beige", style="Casual", season="Cool Weather")
    bottom = make_item(db_session, name="Chinos", category="Bottoms", color="Beige", style="Casual", season="All Season")

    request = RecommendationRequest(
        occasion="Casual",
        weather="Warm",
        wardrobe_item_ids=[warm_top.id, cold_top.id, bottom.id],
        top_k=10,
    )
    result = build_recommendations(db_session, request, test_user_id)

    scores_by_top_id = {}
    for rec in result["recommendations"]:
        for item in rec["items"]:
            if item["id"] in (warm_top.id, cold_top.id):
                scores_by_top_id[item["id"]] = rec["score"]

    assert scores_by_top_id[warm_top.id] > scores_by_top_id[cold_top.id]


def test_anchor_item_is_present_in_every_recommendation(db_session, test_user_id):
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
    result = build_recommendations(db_session, request, test_user_id)

    assert len(result["recommendations"]) >= 1
    for rec in result["recommendations"]:
        item_ids = {item["id"] for item in rec["items"]}
        assert anchor_shoes.id in item_ids


def test_anchor_item_not_found_raises_404(db_session, test_user_id):
    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[], selected_item_id=999999)
    with pytest.raises(HTTPException) as exc_info:
        build_recommendations(db_session, request, test_user_id)
    assert exc_info.value.status_code == 404


def test_deterministic_ranking_same_input_same_output(db_session, test_user_id):
    top = make_item(db_session, name="Shirt", category="Tops", color="Black", style="Formal")
    bottom = make_item(db_session, name="Trouser", category="Bottoms", color="Black", style="Formal")
    shoes = make_item(db_session, name="Shoes", category="Footwear", color="Black", style="Formal")
    accessory = make_item(db_session, name="Belt", category="Accessories", color="Black", style="Formal")

    request = RecommendationRequest(
        occasion="Office",
        wardrobe_item_ids=[top.id, bottom.id, shoes.id, accessory.id],
        top_k=10,
    )

    first = build_recommendations(db_session, request, test_user_id)
    second = build_recommendations(db_session, request, test_user_id)

    assert first["recommendations"] == second["recommendations"]


def test_empty_wardrobe_pool_returns_empty_recommendations_with_message(db_session, test_user_id):
    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[])
    result = build_recommendations(db_session, request, test_user_id)

    assert result["recommendations"] == []
    assert result["message"] is not None
    assert "empty" in result["message"].lower()


def test_nonexistent_wardrobe_ids_returns_empty_with_message(db_session, test_user_id):
    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[12345, 67890])
    result = build_recommendations(db_session, request, test_user_id)

    assert result["recommendations"] == []
    assert result["message"] is not None


def test_insufficient_wardrobe_single_category_returns_no_recommendations(db_session, test_user_id):
    """A lone Accessories item can't satisfy any outfit template on its
    own — no template's required categories are a subset of {Accessories}."""
    accessory = make_item(db_session, name="Watch", category="Accessories", color="Black", style="Formal")

    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[accessory.id])
    result = build_recommendations(db_session, request, test_user_id)

    assert result["recommendations"] == []
    assert "Not enough variety" in result["message"]


def test_partial_outfit_used_when_no_full_template_available(db_session, test_user_id):
    """Tops + Bottoms with no Footwear in the pool should still produce a
    partial outfit, with the explanation noting what's missing."""
    top = make_item(db_session, name="Shirt", category="Tops", color="Black", style="Casual")
    bottom = make_item(db_session, name="Jeans", category="Bottoms", color="Black", style="Casual")

    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[top.id, bottom.id])
    result = build_recommendations(db_session, request, test_user_id)

    assert len(result["recommendations"]) >= 1
    assert "partial outfit" in result["recommendations"][0]["reason"]


def test_missing_optional_accessories_still_produces_a_full_outfit(db_session, test_user_id):
    """A full Tops+Bottoms+Footwear outfit with no Accessories/Outerwear
    anywhere in the pool must still be generated — those slots are
    optional, not required."""
    top = make_item(db_session, name="Shirt", category="Tops", color="Black", style="Casual")
    bottom = make_item(db_session, name="Jeans", category="Bottoms", color="Black", style="Casual")
    shoes = make_item(db_session, name="Shoes", category="Footwear", color="Black", style="Casual")

    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[top.id, bottom.id, shoes.id])
    result = build_recommendations(db_session, request, test_user_id)

    assert len(result["recommendations"]) >= 1
    outfit_ids = {item["id"] for item in result["recommendations"][0]["items"]}
    assert outfit_ids == {top.id, bottom.id, shoes.id}


# --- Phase 3: anchor item that cannot fit any template -----------------------


def test_anchor_item_that_cannot_fit_any_template_returns_clear_message(db_session, test_user_id):
    """An Accessories-only anchor against an otherwise Accessories-only
    pool can't satisfy any template's required categories — the message
    must specifically mention the anchor, not just the generic
    'not enough variety' text."""
    anchor = make_item(db_session, name="Watch", category="Accessories", color="Black", style="Formal")
    other_accessory = make_item(db_session, name="Belt", category="Accessories", color="Brown", style="Formal")

    request = RecommendationRequest(
        occasion="Casual",
        wardrobe_item_ids=[other_accessory.id],
        selected_item_id=anchor.id,
    )
    result = build_recommendations(db_session, request, test_user_id)

    assert result["recommendations"] == []
    assert "anchor item" in result["message"].lower()
    assert anchor.name in result["message"]


# --- Phase 3: color theory actually reaches the ranking ----------------------


def test_complementary_color_relationship_outranks_contrasting_one(db_session, test_user_id):
    """Regression test that app/recommendation/color_theory.py's hue-wheel
    logic is actually wired into scoring, not just unit-tested in
    isolation: blue+yellow (complementary) must outrank blue+red
    (contrasting) when every other dimension is held equal."""
    complementary_top = make_item(db_session, name="Yellow Top", category="Tops", color="Yellow", style="Casual")
    contrasting_top = make_item(db_session, name="Red Top", category="Tops", color="Red", style="Casual")
    blue_bottom = make_item(db_session, name="Blue Bottom", category="Bottoms", color="Blue", style="Casual")

    request = RecommendationRequest(
        occasion="Casual",
        wardrobe_item_ids=[complementary_top.id, contrasting_top.id, blue_bottom.id],
        top_k=10,
        diversify=False,  # isolate the color-theory effect from diversity reranking
    )
    result = build_recommendations(db_session, request, test_user_id)

    scores_by_top_id = {}
    for rec in result["recommendations"]:
        for item in rec["items"]:
            if item["id"] in (complementary_top.id, contrasting_top.id):
                scores_by_top_id[item["id"]] = rec["score"]

    assert scores_by_top_id[complementary_top.id] > scores_by_top_id[contrasting_top.id]


def test_secondary_color_influences_scoring_when_stored(db_session, test_user_id):
    """Regression test that color_theory's secondary-color blending is
    actually reachable end-to-end — not just unit-tested on bare
    ClothingItem objects."""
    plain_top = make_item(db_session, name="Plain Orange", category="Tops", color="Orange")
    multicolor_top = make_item(db_session, name="Orange+White", category="Tops", color="Orange", secondary_color="White")
    navy_bottom = make_item(db_session, name="Navy Bottom", category="Bottoms", color="Navy")

    request = RecommendationRequest(
        occasion="Casual",
        wardrobe_item_ids=[plain_top.id, multicolor_top.id, navy_bottom.id],
        top_k=10,
        diversify=False,
    )
    result = build_recommendations(db_session, request, test_user_id)

    scores_by_top_id = {}
    for rec in result["recommendations"]:
        for item in rec["items"]:
            if item["id"] in (plain_top.id, multicolor_top.id):
                scores_by_top_id[item["id"]] = rec["score"]

    assert scores_by_top_id[multicolor_top.id] != scores_by_top_id[plain_top.id]


def test_low_color_reliability_surfaces_a_caveat(db_session, test_user_id):
    top = make_item(db_session, name="Top", category="Tops", color="Black", color_reliability="low")
    bottom = make_item(db_session, name="Bottom", category="Bottoms", color="White")

    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[top.id, bottom.id], diversify=False)
    result = build_recommendations(db_session, request, test_user_id)

    assert len(result["recommendations"]) >= 1
    caveats = result["recommendations"][0]["caveats"]
    assert any("reliability" in caveat.lower() for caveat in caveats)


# --- Phase 3: personalization reaches ranking end-to-end ---------------------


def test_preferred_color_preference_changes_ranking(db_session, test_user_id):
    preferred_top = make_item(db_session, name="Red Top", category="Tops", color="Red", style="Casual")
    other_top = make_item(db_session, name="Green Top", category="Tops", color="Green", style="Casual")
    bottom = make_item(db_session, name="Bottom", category="Bottoms", color="Grey", style="Casual")

    without_pref = build_recommendations(
        db_session,
        RecommendationRequest(
            occasion="Casual", wardrobe_item_ids=[preferred_top.id, other_top.id, bottom.id], top_k=10
        ),
        test_user_id,
    )
    with_pref = build_recommendations(
        db_session,
        RecommendationRequest(
            occasion="Casual",
            wardrobe_item_ids=[preferred_top.id, other_top.id, bottom.id],
            top_k=10,
            preferred_colors=["Red"],
        ),
        test_user_id,
    )

    def score_for(result, item_id):
        for rec in result["recommendations"]:
            if any(item["id"] == item_id for item in rec["items"]):
                return rec["score"]
        return None

    base_score = score_for(without_pref, preferred_top.id)
    boosted_score = score_for(with_pref, preferred_top.id)
    assert boosted_score > base_score


def test_favorite_preference_is_reflected_in_positive_reasons(db_session, test_user_id):
    favorite_top = make_item(db_session, name="Fav Top", category="Tops", color="Black", is_favorite=True)
    bottom = make_item(db_session, name="Bottom", category="Bottoms", color="White")

    request = RecommendationRequest(
        occasion="Casual", wardrobe_item_ids=[favorite_top.id, bottom.id], prefer_favorites=True, diversify=False,
    )
    result = build_recommendations(db_session, request, test_user_id)

    assert any(
        "favorite" in reason.lower() for reason in result["recommendations"][0]["positive_reasons"]
    )


def test_invalid_preference_value_does_not_crash_the_api(db_session, test_user_id):
    top = make_item(db_session, category="Tops", color="Black")
    bottom = make_item(db_session, category="Bottoms", color="White")

    request = RecommendationRequest(
        occasion="Casual",
        wardrobe_item_ids=[top.id, bottom.id],
        preferred_colors=["not-a-real-color", ""],
        avoided_colors=["also-not-real"],
    )
    result = build_recommendations(db_session, request, test_user_id)  # must not raise
    assert len(result["recommendations"]) >= 1


# --- Phase 3: diversity reduces repetition end-to-end -------------------------


def test_diversity_reduces_repetition_versus_non_diverse_baseline(db_session, test_user_id):
    """A wardrobe deliberately shaped like the real Phase 1/2 baseline
    finding (many near-duplicate outfits available) — diversify=True must
    produce lower average pairwise item-overlap than diversify=False,
    without dropping the single best outfit."""
    tops = [make_item(db_session, name=f"Top {i}", category="Tops", color="Black", style="Formal") for i in range(4)]
    bottoms = [make_item(db_session, name=f"Bottom {i}", category="Bottoms", color="Black", style="Formal") for i in range(4)]
    shoes = make_item(db_session, name="Shoes", category="Footwear", color="Black", style="Formal")

    pool_ids = [i.id for i in tops + bottoms] + [shoes.id]

    diverse = build_recommendations(
        db_session,
        RecommendationRequest(occasion="Office", wardrobe_item_ids=pool_ids, top_k=5, diversify=True),
        test_user_id,
    )
    non_diverse = build_recommendations(
        db_session,
        RecommendationRequest(occasion="Office", wardrobe_item_ids=pool_ids, top_k=5, diversify=False),
        test_user_id,
    )

    def avg_pairwise_overlap(result):
        outfits = [frozenset(item["id"] for item in rec["items"]) for rec in result["recommendations"]]
        overlaps = []
        for i in range(len(outfits)):
            for j in range(i + 1, len(outfits)):
                union = outfits[i] | outfits[j]
                overlaps.append(len(outfits[i] & outfits[j]) / len(union) if union else 0)
        return sum(overlaps) / len(overlaps) if overlaps else 0

    assert avg_pairwise_overlap(diverse) <= avg_pairwise_overlap(non_diverse)
    # Top-ranked outfit must be identical either way — diversity never
    # changes the single best recommendation.
    assert diverse["recommendations"][0]["items"] == non_diverse["recommendations"][0]["items"]


def test_diversity_never_drops_the_anchor_item(db_session, test_user_id):
    anchor = make_item(db_session, name="Anchor Shoes", category="Footwear", color="Red", style="Streetwear")
    tops = [make_item(db_session, name=f"Top {i}", category="Tops", color="Grey", style="Streetwear") for i in range(4)]
    bottoms = [make_item(db_session, name=f"Bottom {i}", category="Bottoms", color="Grey", style="Streetwear") for i in range(4)]

    pool_ids = [i.id for i in tops + bottoms]
    request = RecommendationRequest(
        occasion="Casual", wardrobe_item_ids=pool_ids, selected_item_id=anchor.id, top_k=5, diversify=True,
    )
    result = build_recommendations(db_session, request, test_user_id)

    assert len(result["recommendations"]) >= 1
    for rec in result["recommendations"]:
        assert anchor.id in {item["id"] for item in rec["items"]}


def test_diversity_is_deterministic_end_to_end(db_session, test_user_id):
    tops = [make_item(db_session, name=f"Top {i}", category="Tops", color="Black", style="Formal") for i in range(3)]
    bottoms = [make_item(db_session, name=f"Bottom {i}", category="Bottoms", color="Black", style="Formal") for i in range(3)]
    shoes = make_item(db_session, name="Shoes", category="Footwear", color="Black", style="Formal")

    pool_ids = [i.id for i in tops + bottoms] + [shoes.id]
    request = RecommendationRequest(occasion="Office", wardrobe_item_ids=pool_ids, top_k=5)

    first = build_recommendations(db_session, request, test_user_id)
    second = build_recommendations(db_session, request, test_user_id)
    assert first["recommendations"] == second["recommendations"]


# --- Phase 3: structured explanation consistency ------------------------------


def test_dimension_scores_are_present_and_consistent_with_reason(db_session, test_user_id):
    top = make_item(db_session, category="Tops", color="Black", style="Formal", occasion="Office")
    bottom = make_item(db_session, category="Bottoms", color="White", style="Formal", occasion="Office")

    request = RecommendationRequest(occasion="Office", wardrobe_item_ids=[top.id, bottom.id], diversify=False)
    result = build_recommendations(db_session, request, test_user_id)

    rec = result["recommendations"][0]
    assert set(rec["dimension_scores"].keys()) == {"color", "category", "style", "occasion", "weather", "preference"}
    for value in rec["dimension_scores"].values():
        assert 0.0 <= value <= 1.0
    # High color dimension score should correspond to a positive reason
    # actually mentioning color — never silently inconsistent.
    if rec["dimension_scores"]["color"] >= 0.75:
        assert any("color" in reason.lower() for reason in rec["positive_reasons"])


def test_no_fabricated_reasons_for_low_scoring_dimensions(db_session, test_user_id):
    """A weak/uncertain color pairing must not produce a 'colors complement
    each other'-style positive reason."""
    top = make_item(db_session, category="Tops", color="Purple", style="Casual")
    bottom = make_item(db_session, category="Bottoms", color="Red", style="Casual")  # contrasting, not complementary

    request = RecommendationRequest(occasion="Casual", wardrobe_item_ids=[top.id, bottom.id], diversify=False)
    result = build_recommendations(db_session, request, test_user_id)

    rec = result["recommendations"][0]
    if rec["dimension_scores"]["color"] < 0.75:
        assert not any("colors work well together" in reason.lower() for reason in rec["positive_reasons"])
