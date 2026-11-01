"""API-level integration tests for the health check and wardrobe CRUD
endpoints, run through a real FastAPI TestClient against an isolated
in-memory database (see tests/conftest.py)."""

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


def test_create_clothing_item(client):
    payload = {
        "name": "Blue Jeans",
        "category": "Bottoms",
        "color": "Blue",
        "style": "Casual",
    }
    response = client.post("/wardrobe", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Blue Jeans"
    assert body["wear_count"] == 0
    assert "id" in body and "created_at" in body


def test_list_clothing_items_returns_created_items(client):
    client.post("/wardrobe", json={"name": "Item A", "category": "Tops", "color": "Black", "style": "Casual"})
    client.post("/wardrobe", json={"name": "Item B", "category": "Bottoms", "color": "Grey", "style": "Formal"})

    response = client.get("/wardrobe")
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert names == {"Item A", "Item B"}


def test_get_single_clothing_item(client):
    created = client.post(
        "/wardrobe", json={"name": "Item A", "category": "Tops", "color": "Black", "style": "Casual"}
    ).json()

    response = client.get(f"/wardrobe/{created['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Item A"


def test_get_nonexistent_clothing_item_returns_404(client):
    response = client.get("/wardrobe/999999")
    assert response.status_code == 404


def test_update_clothing_item_partial_update(client):
    created = client.post(
        "/wardrobe",
        json={"name": "Original Name", "category": "Tops", "color": "Black", "style": "Casual"},
    ).json()

    response = client.put(f"/wardrobe/{created['id']}", json={"name": "Updated Name"})
    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Updated Name"
    # Fields not included in the PUT body must be left untouched.
    assert updated["category"] == "Tops"
    assert updated["color"] == "Black"
    assert updated["style"] == "Casual"


def test_create_clothing_item_defaults_is_favorite_false(client):
    created = client.post(
        "/wardrobe", json={"name": "Item", "category": "Tops", "color": "Black", "style": "Casual"}
    ).json()
    assert created["is_favorite"] is False


def test_favorite_toggle_persists_across_requests(client):
    """Regression test for Phase 1's persistent-favourites feature — a
    favourite must survive being re-fetched, not just the immediate
    response (i.e. it's actually stored in the database, not just echoed
    back)."""
    created = client.post(
        "/wardrobe", json={"name": "Item", "category": "Tops", "color": "Black", "style": "Casual"}
    ).json()

    toggle_on = client.put(f"/wardrobe/{created['id']}", json={"is_favorite": True})
    assert toggle_on.status_code == 200
    assert toggle_on.json()["is_favorite"] is True

    refetched = client.get(f"/wardrobe/{created['id']}")
    assert refetched.json()["is_favorite"] is True

    toggle_off = client.put(f"/wardrobe/{created['id']}", json={"is_favorite": False})
    assert toggle_off.json()["is_favorite"] is False


def test_update_nonexistent_clothing_item_returns_404(client):
    response = client.put("/wardrobe/999999", json={"name": "Doesn't matter"})
    assert response.status_code == 404


def test_delete_clothing_item(client):
    created = client.post(
        "/wardrobe", json={"name": "To Delete", "category": "Tops", "color": "Black", "style": "Casual"}
    ).json()

    delete_response = client.delete(f"/wardrobe/{created['id']}")
    assert delete_response.status_code == 200

    get_response = client.get(f"/wardrobe/{created['id']}")
    assert get_response.status_code == 404


def test_delete_nonexistent_clothing_item_returns_404(client):
    response = client.delete("/wardrobe/999999")
    assert response.status_code == 404


def test_replacing_image_deletes_old_file_not_new_one(client):
    """Regression test for Phase 1's image-replacement feature: after
    swapping to a new photo, the OLD file must be gone from disk and the
    NEW one must still be there — no orphan, no data loss."""
    from app.services import image_storage

    old_upload = client.post("/wardrobe/images", files={"file": ("old.jpg", _valid_jpeg_bytes(), "image/jpeg")})
    old_image_url = old_upload.json()["image"]
    old_filename = old_image_url.rsplit("/", 1)[-1]

    created = client.post(
        "/wardrobe",
        json={"name": "Item", "category": "Tops", "color": "Black", "style": "Casual", "image": old_image_url},
    ).json()
    assert (image_storage.UPLOADS_DIR / old_filename).is_file()

    new_upload = client.post("/wardrobe/images", files={"file": ("new.jpg", _valid_jpeg_bytes(), "image/jpeg")})
    new_image_url = new_upload.json()["image"]
    new_filename = new_image_url.rsplit("/", 1)[-1]

    update_response = client.put(f"/wardrobe/{created['id']}", json={"image": new_image_url})
    assert update_response.status_code == 200
    assert update_response.json()["image"] == new_image_url

    assert not (image_storage.UPLOADS_DIR / old_filename).exists()
    assert (image_storage.UPLOADS_DIR / new_filename).is_file()


def test_updating_other_fields_without_image_keeps_existing_file(client):
    """An update that doesn't touch `image` at all must never delete the
    existing photo."""
    from app.services import image_storage

    upload = client.post("/wardrobe/images", files={"file": ("photo.jpg", _valid_jpeg_bytes(), "image/jpeg")})
    image_url = upload.json()["image"]
    filename = image_url.rsplit("/", 1)[-1]

    created = client.post(
        "/wardrobe",
        json={"name": "Item", "category": "Tops", "color": "Black", "style": "Casual", "image": image_url},
    ).json()

    client.put(f"/wardrobe/{created['id']}", json={"name": "Renamed Item"})

    assert (image_storage.UPLOADS_DIR / filename).is_file()


# --- Image upload validation (POST /wardrobe/images) -------------------------


def test_upload_valid_image_succeeds(client):
    files = {"file": ("photo.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    response = client.post("/wardrobe/images", files=files)
    assert response.status_code == 200
    assert response.json()["image"].startswith("/uploads/")


def test_upload_invalid_content_type_rejected(client):
    files = {"file": ("doc.pdf", b"%PDF-1.4 not a real pdf", "application/pdf")}
    response = client.post("/wardrobe/images", files=files)
    assert response.status_code == 415


def test_upload_oversized_image_rejected(client):
    # Content-type is valid; size alone must trigger rejection before any
    # attempt to decode the (deliberately garbage) bytes as an image.
    oversized = b"\xff" * (10 * 1024 * 1024 + 1)
    files = {"file": ("huge.jpg", oversized, "image/jpeg")}
    response = client.post("/wardrobe/images", files=files)
    assert response.status_code == 413


def test_upload_invalid_image_content_rejected(client):
    # Correct content-type and an acceptable size, but the bytes are not a
    # decodable image at all.
    files = {"file": ("fake.jpg", b"this is not an image file", "image/jpeg")}
    response = client.post("/wardrobe/images", files=files)
    assert response.status_code == 400


def test_upload_empty_file_rejected(client):
    files = {"file": ("empty.jpg", b"", "image/jpeg")}
    response = client.post("/wardrobe/images", files=files)
    assert response.status_code == 400
