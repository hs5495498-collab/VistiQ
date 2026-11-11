"""API-level integration tests for the health check and wardrobe CRUD
endpoints, run through a real FastAPI TestClient against an isolated
in-memory database (see tests/conftest.py).

Phase 4: every wardrobe-mutating/-reading test now uses
`authenticated_client` (logged in as a default test user, CSRF header
pre-configured) instead of the raw `client` — except the handful of tests
that specifically check unauthenticated/cross-user behavior, which use
`client` and `second_authenticated_client` on purpose."""

import io

from PIL import Image


def _valid_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=(10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_create_clothing_item(authenticated_client):
    payload = {
        "name": "Blue Jeans",
        "category": "Bottoms",
        "color": "Blue",
        "style": "Casual",
    }
    response = authenticated_client.post("/wardrobe", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Blue Jeans"
    assert body["wear_count"] == 0
    assert "id" in body and "created_at" in body


def test_list_clothing_items_returns_created_items(authenticated_client):
    authenticated_client.post("/wardrobe", json={"name": "Item A", "category": "Tops", "color": "Black", "style": "Casual"})
    authenticated_client.post("/wardrobe", json={"name": "Item B", "category": "Bottoms", "color": "Grey", "style": "Formal"})

    response = authenticated_client.get("/wardrobe")
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert names == {"Item A", "Item B"}


def test_get_single_clothing_item(authenticated_client):
    created = authenticated_client.post(
        "/wardrobe", json={"name": "Item A", "category": "Tops", "color": "Black", "style": "Casual"}
    ).json()

    response = authenticated_client.get(f"/wardrobe/{created['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Item A"


def test_get_nonexistent_clothing_item_returns_404(authenticated_client):
    response = authenticated_client.get("/wardrobe/999999")
    assert response.status_code == 404


def test_update_clothing_item_partial_update(authenticated_client):
    created = authenticated_client.post(
        "/wardrobe",
        json={"name": "Original Name", "category": "Tops", "color": "Black", "style": "Casual"},
    ).json()

    response = authenticated_client.put(f"/wardrobe/{created['id']}", json={"name": "Updated Name"})
    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Updated Name"
    # Fields not included in the PUT body must be left untouched.
    assert updated["category"] == "Tops"
    assert updated["color"] == "Black"
    assert updated["style"] == "Casual"


def test_create_clothing_item_defaults_is_favorite_false(authenticated_client):
    created = authenticated_client.post(
        "/wardrobe", json={"name": "Item", "category": "Tops", "color": "Black", "style": "Casual"}
    ).json()
    assert created["is_favorite"] is False


def test_favorite_toggle_persists_across_requests(authenticated_client):
    """Regression test for Phase 1's persistent-favourites feature — a
    favourite must survive being re-fetched, not just the immediate
    response (i.e. it's actually stored in the database, not just echoed
    back)."""
    created = authenticated_client.post(
        "/wardrobe", json={"name": "Item", "category": "Tops", "color": "Black", "style": "Casual"}
    ).json()

    toggle_on = authenticated_client.put(f"/wardrobe/{created['id']}", json={"is_favorite": True})
    assert toggle_on.status_code == 200
    assert toggle_on.json()["is_favorite"] is True

    refetched = authenticated_client.get(f"/wardrobe/{created['id']}")
    assert refetched.json()["is_favorite"] is True

    toggle_off = authenticated_client.put(f"/wardrobe/{created['id']}", json={"is_favorite": False})
    assert toggle_off.json()["is_favorite"] is False


def test_update_nonexistent_clothing_item_returns_404(authenticated_client):
    response = authenticated_client.put("/wardrobe/999999", json={"name": "Doesn't matter"})
    assert response.status_code == 404


def test_delete_clothing_item(authenticated_client):
    created = authenticated_client.post(
        "/wardrobe", json={"name": "To Delete", "category": "Tops", "color": "Black", "style": "Casual"}
    ).json()

    delete_response = authenticated_client.delete(f"/wardrobe/{created['id']}")
    assert delete_response.status_code == 200

    get_response = authenticated_client.get(f"/wardrobe/{created['id']}")
    assert get_response.status_code == 404


def test_deleting_item_removes_its_uploaded_image_file(authenticated_client):
    """Regression test — `delete_clothing_item` calls `delete_clothing_image`
    after the DB row is gone, but that cleanup path had no direct test
    coverage (test_delete_clothing_item above never attaches an image)."""
    from app.services import image_storage

    upload = authenticated_client.post(
        "/wardrobe/images", files={"file": ("photo.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    )
    image_url = upload.json()["image"]
    filename = image_url.rsplit("/", 1)[-1]

    created = authenticated_client.post(
        "/wardrobe",
        json={"name": "Item", "category": "Tops", "color": "Black", "style": "Casual", "image": image_url},
    ).json()
    assert (image_storage.UPLOADS_DIR / filename).is_file()

    delete_response = authenticated_client.delete(f"/wardrobe/{created['id']}")
    assert delete_response.status_code == 200
    assert not (image_storage.UPLOADS_DIR / filename).exists()


def test_delete_nonexistent_clothing_item_returns_404(authenticated_client):
    response = authenticated_client.delete("/wardrobe/999999")
    assert response.status_code == 404


def test_replacing_image_deletes_old_file_not_new_one(authenticated_client):
    """Regression test for Phase 1's image-replacement feature: after
    swapping to a new photo, the OLD file must be gone from disk and the
    NEW one must still be there — no orphan, no data loss."""
    from app.services import image_storage

    old_upload = authenticated_client.post(
        "/wardrobe/images", files={"file": ("old.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    )
    old_image_url = old_upload.json()["image"]
    old_filename = old_image_url.rsplit("/", 1)[-1]

    created = authenticated_client.post(
        "/wardrobe",
        json={"name": "Item", "category": "Tops", "color": "Black", "style": "Casual", "image": old_image_url},
    ).json()
    assert (image_storage.UPLOADS_DIR / old_filename).is_file()

    new_upload = authenticated_client.post(
        "/wardrobe/images", files={"file": ("new.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    )
    new_image_url = new_upload.json()["image"]
    new_filename = new_image_url.rsplit("/", 1)[-1]

    update_response = authenticated_client.put(f"/wardrobe/{created['id']}", json={"image": new_image_url})
    assert update_response.status_code == 200
    assert update_response.json()["image"] == new_image_url

    assert not (image_storage.UPLOADS_DIR / old_filename).exists()
    assert (image_storage.UPLOADS_DIR / new_filename).is_file()


def test_updating_other_fields_without_image_keeps_existing_file(authenticated_client):
    """An update that doesn't touch `image` at all must never delete the
    existing photo."""
    from app.services import image_storage

    upload = authenticated_client.post(
        "/wardrobe/images", files={"file": ("photo.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    )
    image_url = upload.json()["image"]
    filename = image_url.rsplit("/", 1)[-1]

    created = authenticated_client.post(
        "/wardrobe",
        json={"name": "Item", "category": "Tops", "color": "Black", "style": "Casual", "image": image_url},
    ).json()

    authenticated_client.put(f"/wardrobe/{created['id']}", json={"name": "Renamed Item"})

    assert (image_storage.UPLOADS_DIR / filename).is_file()


# --- Image upload validation (POST /wardrobe/images) -------------------------


def test_upload_valid_image_succeeds(authenticated_client):
    files = {"file": ("photo.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    response = authenticated_client.post("/wardrobe/images", files=files)
    assert response.status_code == 200
    assert response.json()["image"].startswith("/wardrobe/images/")


def test_upload_invalid_content_type_rejected(authenticated_client):
    files = {"file": ("doc.pdf", b"%PDF-1.4 not a real pdf", "application/pdf")}
    response = authenticated_client.post("/wardrobe/images", files=files)
    assert response.status_code == 415


def test_upload_oversized_image_rejected(authenticated_client):
    # Content-type is valid; size alone must trigger rejection before any
    # attempt to decode the (deliberately garbage) bytes as an image.
    oversized = b"\xff" * (10 * 1024 * 1024 + 1)
    files = {"file": ("huge.jpg", oversized, "image/jpeg")}
    response = authenticated_client.post("/wardrobe/images", files=files)
    assert response.status_code == 413


def test_upload_invalid_image_content_rejected(authenticated_client):
    # Correct content-type and an acceptable size, but the bytes are not a
    # decodable image at all.
    files = {"file": ("fake.jpg", b"this is not an image file", "image/jpeg")}
    response = authenticated_client.post("/wardrobe/images", files=files)
    assert response.status_code == 400


def test_upload_empty_file_rejected(authenticated_client):
    files = {"file": ("empty.jpg", b"", "image/jpeg")}
    response = authenticated_client.post("/wardrobe/images", files=files)
    assert response.status_code == 400


# --- Phase 4: authentication / authorization ----------------------------------


def test_unauthenticated_list_wardrobe_is_rejected(client):
    assert client.get("/wardrobe").status_code == 401


def test_unauthenticated_create_wardrobe_item_is_rejected(client):
    response = client.post("/wardrobe", json={"name": "Item", "category": "Tops", "color": "Black", "style": "Casual"})
    assert response.status_code == 401


def test_unauthenticated_image_upload_is_rejected(client):
    files = {"file": ("photo.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    assert client.post("/wardrobe/images", files=files).status_code == 401


def test_user_b_cannot_read_user_a_item(authenticated_client, second_authenticated_client):
    item_a = authenticated_client.post(
        "/wardrobe", json={"name": "User A's Shirt", "category": "Tops", "color": "Black", "style": "Casual"}
    ).json()

    response = second_authenticated_client.get(f"/wardrobe/{item_a['id']}")
    assert response.status_code == 404  # never a 403 — never confirms it exists


def test_user_b_cannot_see_user_a_item_in_list(authenticated_client, second_authenticated_client):
    authenticated_client.post(
        "/wardrobe", json={"name": "User A's Shirt", "category": "Tops", "color": "Black", "style": "Casual"}
    )
    response = second_authenticated_client.get("/wardrobe")
    assert response.status_code == 200
    assert response.json() == []


def test_user_b_cannot_update_user_a_item(authenticated_client, second_authenticated_client):
    item_a = authenticated_client.post(
        "/wardrobe", json={"name": "User A's Shirt", "category": "Tops", "color": "Black", "style": "Casual"}
    ).json()

    response = second_authenticated_client.put(f"/wardrobe/{item_a['id']}", json={"name": "Hijacked"})
    assert response.status_code == 404

    # Confirm the item is genuinely untouched.
    still_a = authenticated_client.get(f"/wardrobe/{item_a['id']}").json()
    assert still_a["name"] == "User A's Shirt"


def test_user_b_cannot_delete_user_a_item(authenticated_client, second_authenticated_client):
    item_a = authenticated_client.post(
        "/wardrobe", json={"name": "User A's Shirt", "category": "Tops", "color": "Black", "style": "Casual"}
    ).json()

    response = second_authenticated_client.delete(f"/wardrobe/{item_a['id']}")
    assert response.status_code == 404

    still_there = authenticated_client.get(f"/wardrobe/{item_a['id']}")
    assert still_there.status_code == 200


def test_user_b_cannot_favorite_user_a_item(authenticated_client, second_authenticated_client):
    item_a = authenticated_client.post(
        "/wardrobe", json={"name": "User A's Shirt", "category": "Tops", "color": "Black", "style": "Casual"}
    ).json()

    response = second_authenticated_client.put(f"/wardrobe/{item_a['id']}", json={"is_favorite": True})
    assert response.status_code == 404


def test_user_b_cannot_access_user_a_image(authenticated_client, second_authenticated_client):
    upload = authenticated_client.post(
        "/wardrobe/images", files={"file": ("photo.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    )
    image_url = upload.json()["image"]
    authenticated_client.post(
        "/wardrobe",
        json={"name": "User A's Shirt", "category": "Tops", "color": "Black", "style": "Casual", "image": image_url},
    )

    response = second_authenticated_client.get(image_url)
    assert response.status_code == 404

    # The owner can still fetch their own image.
    own_response = authenticated_client.get(image_url)
    assert own_response.status_code == 200


def test_mutating_request_without_csrf_header_is_rejected(client):
    """A logged-in client that forgot/was tricked out of sending the CSRF
    header must be rejected — even though its session cookie alone is
    otherwise valid."""
    client.post(
        "/auth/register",
        json={"name": "No CSRF", "email": "no-csrf@example.com", "password": "irrelevant123", "password_confirmation": "irrelevant123"},
    )
    # Deliberately NOT setting the X-CSRF-Token header this client received.
    response = client.post("/wardrobe", json={"name": "Item", "category": "Tops", "color": "Black", "style": "Casual"})
    assert response.status_code == 403
