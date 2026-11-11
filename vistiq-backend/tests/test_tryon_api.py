"""API-level integration tests for the virtual try-on endpoints (Phase 5 —
experimental), run through a real FastAPI TestClient against an isolated
in-memory database (see tests/conftest.py).

The GPU worker itself is always mocked here (monkeypatching
app.services.tryon_worker.run_tryon / is_worker_configured) — these tests
verify VISTIQ's own job lifecycle, ownership, and error handling, never
real CatVTON inference. That is covered separately, manually, in Colab (see
docs/virtual-tryon.md); it is NOT exercised by this automated suite.
"""

import io
from datetime import datetime

from PIL import Image

from app.database.models import TryOnJob
from app.routes.tryon import recover_interrupted_jobs
from app.services import tryon_worker


def _valid_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=(10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def _create_garment(authenticated_client) -> int:
    """Creates a wardrobe item with a real uploaded photo attached — a
    try-on job requires the garment to actually have an image."""
    image_url = authenticated_client.post(
        "/wardrobe/images", files={"file": ("garment.jpg", _valid_jpeg_bytes(), "image/jpeg")}
    ).json()["image"]
    item = authenticated_client.post(
        "/wardrobe",
        json={"name": "Try-On Garment", "category": "Tops", "color": "Blue", "style": "Casual", "image": image_url},
    ).json()
    return item["id"]


def _person_files():
    return {"person_image": ("person.jpg", _valid_jpeg_bytes(), "image/jpeg")}


# --- Authentication / CSRF ---------------------------------------------------


def test_create_tryon_job_requires_authentication(client):
    response = client.post(
        "/tryon", data={"garment_item_id": "1", "cloth_type": "upper"}, files=_person_files()
    )
    assert response.status_code == 401


def test_list_tryon_jobs_requires_authentication(client):
    assert client.get("/tryon").status_code == 401


def test_create_tryon_job_without_csrf_header_is_rejected(authenticated_client):
    garment_id = _create_garment(authenticated_client)
    headers = dict(authenticated_client.headers)
    del authenticated_client.headers["X-CSRF-Token"]
    try:
        response = authenticated_client.post(
            "/tryon",
            data={"garment_item_id": str(garment_id), "cloth_type": "upper"},
            files=_person_files(),
        )
        assert response.status_code == 403
    finally:
        authenticated_client.headers.update(headers)


def test_delete_tryon_job_without_csrf_header_is_rejected(authenticated_client, monkeypatch):
    monkeypatch.setattr(tryon_worker, "is_worker_configured", lambda: False)
    garment_id = _create_garment(authenticated_client)
    job_id = authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "upper"}, files=_person_files()
    ).json()["id"]

    headers = dict(authenticated_client.headers)
    del authenticated_client.headers["X-CSRF-Token"]
    try:
        assert authenticated_client.delete(f"/tryon/{job_id}").status_code == 403
    finally:
        authenticated_client.headers.update(headers)


# --- Input validation ---------------------------------------------------------


def test_create_tryon_job_rejects_invalid_cloth_type(authenticated_client):
    garment_id = _create_garment(authenticated_client)
    response = authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "not-a-real-type"}, files=_person_files()
    )
    assert response.status_code == 400


def test_create_tryon_job_rejects_nonexistent_garment(authenticated_client):
    response = authenticated_client.post(
        "/tryon", data={"garment_item_id": "999999", "cloth_type": "upper"}, files=_person_files()
    )
    assert response.status_code == 404


def test_create_tryon_job_rejects_garment_without_photo(authenticated_client):
    item = authenticated_client.post(
        "/wardrobe", json={"name": "No Photo", "category": "Tops", "color": "Blue", "style": "Casual"}
    ).json()
    response = authenticated_client.post(
        "/tryon", data={"garment_item_id": str(item["id"]), "cloth_type": "upper"}, files=_person_files()
    )
    assert response.status_code == 400


def test_create_tryon_job_rejects_non_image_person_upload(authenticated_client):
    garment_id = _create_garment(authenticated_client)
    response = authenticated_client.post(
        "/tryon",
        data={"garment_item_id": str(garment_id), "cloth_type": "upper"},
        files={"person_image": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415


# --- Cross-user isolation -----------------------------------------------------


def test_cannot_create_tryon_job_for_another_users_garment(authenticated_client, second_authenticated_client):
    garment_id = _create_garment(authenticated_client)
    response = second_authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "upper"}, files=_person_files()
    )
    assert response.status_code == 404


def test_cannot_view_another_users_job(authenticated_client, second_authenticated_client, monkeypatch):
    monkeypatch.setattr(tryon_worker, "is_worker_configured", lambda: False)
    garment_id = _create_garment(authenticated_client)
    job_id = authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "upper"}, files=_person_files()
    ).json()["id"]

    assert second_authenticated_client.get(f"/tryon/{job_id}").status_code == 404
    assert second_authenticated_client.delete(f"/tryon/{job_id}").status_code == 404


def test_cannot_list_another_users_jobs(authenticated_client, second_authenticated_client, monkeypatch):
    monkeypatch.setattr(tryon_worker, "is_worker_configured", lambda: False)
    garment_id = _create_garment(authenticated_client)
    authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "upper"}, files=_person_files()
    )

    assert second_authenticated_client.get("/tryon").json() == []


def test_cannot_view_another_users_result_image(authenticated_client, second_authenticated_client, monkeypatch):
    # The worker call happens in a BackgroundTask, which Starlette's
    # TestClient runs to completion before .post() returns control here —
    # but the POST *response body* was already serialized from the job's
    # state at creation time ("pending"), before that task ran. A GET
    # afterward reflects the now-finished state; this is correct async-job
    # API behavior, not a quirk of the test.
    monkeypatch.setattr(tryon_worker, "is_worker_configured", lambda: True)
    monkeypatch.setattr(tryon_worker, "run_tryon", lambda *a, **k: _valid_jpeg_bytes())
    garment_id = _create_garment(authenticated_client)
    created = authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "upper"}, files=_person_files()
    ).json()
    job = authenticated_client.get(f"/tryon/{created['id']}").json()
    assert job["status"] == "completed"
    filename = job["result_image"].rsplit("/", 1)[-1]

    assert second_authenticated_client.get(f"/tryon/results/{filename}").status_code == 404
    # The owner, however, can see it.
    assert authenticated_client.get(f"/tryon/results/{filename}").status_code == 200


# --- Job lifecycle / status transitions --------------------------------------


def test_worker_unavailable_marks_job_failed_immediately(authenticated_client, monkeypatch):
    monkeypatch.setattr(tryon_worker, "is_worker_configured", lambda: False)
    garment_id = _create_garment(authenticated_client)

    response = authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "upper"}, files=_person_files()
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert "unavailable" in body["error_message"].lower()
    assert body["result_image"] is None
    assert body["completed_at"] is not None


def test_successful_worker_call_marks_job_completed(authenticated_client, monkeypatch):
    monkeypatch.setattr(tryon_worker, "is_worker_configured", lambda: True)
    monkeypatch.setattr(tryon_worker, "run_tryon", lambda *a, **k: _valid_jpeg_bytes())
    garment_id = _create_garment(authenticated_client)

    created = authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "upper"}, files=_person_files()
    ).json()
    assert created["status"] == "pending"  # the POST response reflects creation time, before the worker runs

    # By the time .post() above returned, Starlette's TestClient had already
    # run the BackgroundTask to completion — this GET reflects that.
    body = authenticated_client.get(f"/tryon/{created['id']}").json()
    assert body["status"] == "completed"
    assert body["result_image"] is not None
    assert body["error_message"] is None


def test_worker_error_marks_job_failed_with_safe_message(authenticated_client, monkeypatch):
    def _raise(*_args, **_kwargs):
        raise tryon_worker.TryOnWorkerError("The virtual try-on worker could not process this request.")

    monkeypatch.setattr(tryon_worker, "is_worker_configured", lambda: True)
    monkeypatch.setattr(tryon_worker, "run_tryon", _raise)
    garment_id = _create_garment(authenticated_client)

    created = authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "upper"}, files=_person_files()
    ).json()
    body = authenticated_client.get(f"/tryon/{created['id']}").json()
    assert body["status"] == "failed"
    assert body["error_message"] == "The virtual try-on worker could not process this request."


def test_worker_timeout_marks_job_failed(authenticated_client, monkeypatch):
    def _raise_timeout(*_args, **_kwargs):
        raise tryon_worker.TryOnWorkerError(
            "The virtual try-on worker took too long to respond. Please try again."
        )

    monkeypatch.setattr(tryon_worker, "is_worker_configured", lambda: True)
    monkeypatch.setattr(tryon_worker, "run_tryon", _raise_timeout)
    garment_id = _create_garment(authenticated_client)

    created = authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "upper"}, files=_person_files()
    ).json()
    body = authenticated_client.get(f"/tryon/{created['id']}").json()
    assert body["status"] == "failed"
    assert "too long" in body["error_message"]


def test_unexpected_worker_exception_never_leaks_internal_details(authenticated_client, monkeypatch):
    def _raise_unexpected(*_args, **_kwargs):
        raise RuntimeError("CUDA out of memory at /content/CatVTON/model/pipeline.py line 212")

    monkeypatch.setattr(tryon_worker, "is_worker_configured", lambda: True)
    monkeypatch.setattr(tryon_worker, "run_tryon", _raise_unexpected)
    garment_id = _create_garment(authenticated_client)

    created = authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "upper"}, files=_person_files()
    ).json()
    body = authenticated_client.get(f"/tryon/{created['id']}").json()
    assert body["status"] == "failed"
    assert "CUDA" not in body["error_message"]
    assert "pipeline.py" not in body["error_message"]


def test_missing_result_image_returns_404_before_completion(authenticated_client, monkeypatch):
    monkeypatch.setattr(tryon_worker, "is_worker_configured", lambda: False)
    garment_id = _create_garment(authenticated_client)
    job = authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "upper"}, files=_person_files()
    ).json()
    assert job["result_image"] is None  # failed immediately, nothing to fetch

    assert authenticated_client.get("/tryon/results/does-not-exist.png").status_code == 404


# --- Persistence / listing ----------------------------------------------------


def test_database_persistence_across_requests(authenticated_client, monkeypatch):
    monkeypatch.setattr(tryon_worker, "is_worker_configured", lambda: False)
    garment_id = _create_garment(authenticated_client)
    created = authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "upper"}, files=_person_files()
    ).json()

    fetched = authenticated_client.get(f"/tryon/{created['id']}").json()
    assert fetched == created

    listed = authenticated_client.get("/tryon").json()
    assert any(j["id"] == created["id"] for j in listed)


def test_get_nonexistent_job_returns_404(authenticated_client):
    assert authenticated_client.get("/tryon/999999").status_code == 404


# --- Safe deletion and cleanup -------------------------------------------------


def test_delete_job_removes_it_and_its_images(authenticated_client, monkeypatch):
    monkeypatch.setattr(tryon_worker, "is_worker_configured", lambda: True)
    monkeypatch.setattr(tryon_worker, "run_tryon", lambda *a, **k: _valid_jpeg_bytes())
    garment_id = _create_garment(authenticated_client)
    created = authenticated_client.post(
        "/tryon", data={"garment_item_id": str(garment_id), "cloth_type": "upper"}, files=_person_files()
    ).json()
    job = authenticated_client.get(f"/tryon/{created['id']}").json()
    result_filename = job["result_image"].rsplit("/", 1)[-1]

    delete_response = authenticated_client.delete(f"/tryon/{job['id']}")
    assert delete_response.status_code == 200
    assert authenticated_client.get(f"/tryon/{job['id']}").status_code == 404
    assert authenticated_client.get(f"/tryon/results/{result_filename}").status_code == 404


def test_delete_nonexistent_job_returns_404(authenticated_client):
    assert authenticated_client.delete("/tryon/999999").status_code == 404


# --- Startup recovery of jobs orphaned by a server crash -----------------------


def test_recover_interrupted_jobs_fails_pending_and_processing_but_leaves_terminal_jobs_alone(
    db_session, test_user_id
):
    pending = TryOnJob(user_id=test_user_id, person_image="/tryon/person-images/a.png", status="pending")
    processing = TryOnJob(user_id=test_user_id, person_image="/tryon/person-images/b.png", status="processing")
    completed = TryOnJob(
        user_id=test_user_id,
        person_image="/tryon/person-images/c.png",
        result_image="/tryon/results/c.png",
        status="completed",
        completed_at=datetime.utcnow(),
    )
    failed = TryOnJob(
        user_id=test_user_id,
        person_image="/tryon/person-images/d.png",
        status="failed",
        error_message="some earlier real failure",
        completed_at=datetime.utcnow(),
    )
    db_session.add_all([pending, processing, completed, failed])
    db_session.commit()

    recovered_count = recover_interrupted_jobs(db_session)
    assert recovered_count == 2

    db_session.refresh(pending)
    db_session.refresh(processing)
    db_session.refresh(completed)
    db_session.refresh(failed)

    for job in (pending, processing):
        assert job.status == "failed"
        assert job.error_message == "Virtual try-on was interrupted by a server restart. Please try again."
        assert job.completed_at is not None

    # Already-terminal jobs are left completely untouched.
    assert completed.status == "completed"
    assert completed.error_message is None
    assert failed.status == "failed"
    assert failed.error_message == "some earlier real failure"


def test_recover_interrupted_jobs_is_a_no_op_when_nothing_is_orphaned(db_session, test_user_id):
    completed = TryOnJob(
        user_id=test_user_id,
        person_image="/tryon/person-images/e.png",
        result_image="/tryon/results/e.png",
        status="completed",
        completed_at=datetime.utcnow(),
    )
    db_session.add(completed)
    db_session.commit()

    assert recover_interrupted_jobs(db_session) == 0
    db_session.refresh(completed)
    assert completed.status == "completed"
