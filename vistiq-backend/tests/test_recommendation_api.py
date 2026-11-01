"""API-level tests for POST /recommend, through the real FastAPI
TestClient — complementing tests/test_recommendation_engine.py (which
calls build_recommendations() directly). Focused on backward compatibility
and the new Phase 3 request/response fields at the HTTP boundary."""


def _create_item(authenticated_client, **overrides):
    payload = {"name": "Item", "category": "Tops", "color": "Black", "style": "Casual"}
    payload.update(overrides)
    return authenticated_client.post("/wardrobe", json=payload).json()


def test_existing_minimal_request_shape_still_works(authenticated_client):
    """A request using ONLY the fields that existed before Phase 3 must
    still succeed — none of the new fields are required."""
    top = _create_item(authenticated_client, category="Tops", color="Black")
    bottom = _create_item(authenticated_client, category="Bottoms", color="White")

    response = authenticated_client.post(
        "/recommend",
        json={"occasion": "Casual", "wardrobe_item_ids": [top["id"], bottom["id"]], "top_k": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["recommendations"]) >= 1


def test_response_includes_phase3_structured_fields_with_safe_defaults(authenticated_client):
    top = _create_item(authenticated_client, category="Tops", color="Black")
    bottom = _create_item(authenticated_client, category="Bottoms", color="White")

    response = authenticated_client.post(
        "/recommend", json={"occasion": "Casual", "wardrobe_item_ids": [top["id"], bottom["id"]]}
    )
    assert response.status_code == 200
    rec = response.json()["recommendations"][0]
    assert "dimension_scores" in rec and isinstance(rec["dimension_scores"], dict)
    assert "positive_reasons" in rec and isinstance(rec["positive_reasons"], list)
    assert "caveats" in rec and isinstance(rec["caveats"], list)
    assert "reason" in rec  # original field, unchanged


def test_new_preference_fields_are_accepted_over_http(authenticated_client):
    top = _create_item(authenticated_client, category="Tops", color="Red")
    bottom = _create_item(authenticated_client, category="Bottoms", color="Grey")

    response = authenticated_client.post(
        "/recommend",
        json={
            "occasion": "Casual",
            "wardrobe_item_ids": [top["id"], bottom["id"]],
            "preferred_colors": ["Red"],
            "avoided_colors": ["Pink"],
            "prefer_favorites": True,
            "diversify": False,
        },
    )
    assert response.status_code == 200
    assert len(response.json()["recommendations"]) >= 1


def test_malformed_preference_type_returns_422_not_500(authenticated_client):
    """Pydantic validation (not a crash) for a structurally wrong
    preference value — a string where a list was expected."""
    top = _create_item(authenticated_client)
    response = authenticated_client.post(
        "/recommend",
        json={"occasion": "Casual", "wardrobe_item_ids": [top["id"]], "preferred_colors": "Red"},
    )
    assert response.status_code == 422


def test_anchor_item_present_in_every_outfit_over_http(authenticated_client):
    anchor = _create_item(authenticated_client, name="Anchor Shoes", category="Footwear", color="Red")
    top = _create_item(authenticated_client, category="Tops", color="Grey")
    bottom = _create_item(authenticated_client, category="Bottoms", color="Grey")

    response = authenticated_client.post(
        "/recommend",
        json={
            "occasion": "Casual",
            "wardrobe_item_ids": [top["id"], bottom["id"]],
            "selected_item_id": anchor["id"],
            "top_k": 5,
        },
    )
    assert response.status_code == 200
    recommendations = response.json()["recommendations"]
    assert len(recommendations) >= 1
    for rec in recommendations:
        assert anchor["id"] in {item["id"] for item in rec["items"]}


def test_favorite_item_preference_over_http(authenticated_client):
    favorite_top = _create_item(authenticated_client, category="Tops", color="Black", is_favorite=True)
    bottom = _create_item(authenticated_client, category="Bottoms", color="White")

    response = authenticated_client.post(
        "/recommend",
        json={
            "occasion": "Casual",
            "wardrobe_item_ids": [favorite_top["id"], bottom["id"]],
            "prefer_favorites": True,
            "diversify": False,
        },
    )
    assert response.status_code == 200
    rec = response.json()["recommendations"][0]
    assert any("favorite" in reason.lower() for reason in rec["positive_reasons"])


# --- Phase 4: authentication / authorization ----------------------------------


def test_unauthenticated_recommend_request_is_rejected(client):
    response = client.post("/recommend", json={"occasion": "Casual", "wardrobe_item_ids": [1]})
    assert response.status_code == 401


def test_user_b_cannot_generate_recommendations_from_user_a_wardrobe(authenticated_client, second_authenticated_client):
    top = _create_item(authenticated_client, category="Tops", color="Black")
    bottom = _create_item(authenticated_client, category="Bottoms", color="White")

    response = second_authenticated_client.post(
        "/recommend", json={"occasion": "Casual", "wardrobe_item_ids": [top["id"], bottom["id"]]}
    )
    assert response.status_code == 200
    # User B's request names User A's item ids, but none of THEIR items
    # match (user-scoped query), so no outfit can be built from them.
    assert response.json()["recommendations"] == []


def test_user_b_cannot_use_user_a_item_as_anchor(authenticated_client, second_authenticated_client):
    anchor = _create_item(authenticated_client, name="User A's Shoes", category="Footwear", color="Red")

    response = second_authenticated_client.post(
        "/recommend", json={"occasion": "Casual", "wardrobe_item_ids": [], "selected_item_id": anchor["id"]}
    )
    assert response.status_code == 404
