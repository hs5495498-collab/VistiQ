"""Local persistent storage for virtual try-on person photos and generated
results (Phase 5 — experimental). Same approach as
app/services/image_storage.py: server-generated filenames only, served back
through an authenticated, ownership-checked route
(app/routes/tryon.py:get_tryon_person_image / get_tryon_result_image), never
a public StaticFiles mount.

Kept in its own directories (not data/uploads) so a wardrobe-item delete and
a try-on-job delete can never accidentally race on the same file, and so
this experimental feature's files are trivially identifiable/removable as a
unit if the feature is ever pulled out.
"""

import uuid
from pathlib import Path

from app.services.image_validation import CONTENT_TYPE_EXTENSIONS

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PERSON_IMAGES_DIR = BASE_DIR / "data" / "tryon_person_images"
RESULT_IMAGES_DIR = BASE_DIR / "data" / "tryon_results"
PERSON_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
RESULT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

PERSON_IMAGE_URL_PREFIX = "/tryon/person-images"
RESULT_IMAGE_URL_PREFIX = "/tryon/results"


def save_person_image(raw_bytes: bytes, content_type: str) -> str:
    """Persists an already-validated uploaded person photo. Returns the
    servable relative URL, stored on TryOnJob.person_image."""
    extension = CONTENT_TYPE_EXTENSIONS[content_type]
    filename = f"{uuid.uuid4().hex}{extension}"
    (PERSON_IMAGES_DIR / filename).write_bytes(raw_bytes)
    return f"{PERSON_IMAGE_URL_PREFIX}/{filename}"


def save_result_image(raw_bytes: bytes) -> str:
    """Persists a generated try-on result (always PNG — the worker returns
    PNG bytes, see app/services/tryon_worker.py). Returns the servable
    relative URL, stored on TryOnJob.result_image."""
    filename = f"{uuid.uuid4().hex}.png"
    (RESULT_IMAGES_DIR / filename).write_bytes(raw_bytes)
    return f"{RESULT_IMAGE_URL_PREFIX}/{filename}"


def _delete_under(image_url: str | None, prefix: str, directory: Path) -> None:
    """Shared best-effort delete, identical safety reasoning to
    app/services/image_storage.py:delete_clothing_image() — never raises,
    never follows a path outside `directory`."""
    url_prefix = f"{prefix}/"
    if not image_url or not image_url.startswith(url_prefix):
        return

    filename = image_url[len(url_prefix):]
    if not filename or "/" in filename or "\\" in filename or filename in {".", ".."}:
        return

    file_path = directory / filename
    try:
        if file_path.is_file() and file_path.resolve().parent == directory.resolve():
            file_path.unlink()
    except OSError:
        pass


def delete_person_image(image_url: str | None) -> None:
    _delete_under(image_url, PERSON_IMAGE_URL_PREFIX, PERSON_IMAGES_DIR)


def delete_result_image(image_url: str | None) -> None:
    _delete_under(image_url, RESULT_IMAGE_URL_PREFIX, RESULT_IMAGES_DIR)
