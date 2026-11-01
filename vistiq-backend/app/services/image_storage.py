"""Local persistent storage for uploaded wardrobe photos (Stage 16).

Deliberately simple for a PBL prototype: files are saved to a local
directory and served back via FastAPI's StaticFiles mount (see app/main.py)
— no cloud storage, no database blobs. Filenames are always generated
server-side (uuid4 + an extension derived from the validated content-type),
never taken from the client, so a malicious/odd original filename can never
reach the filesystem.
"""

import uuid
from pathlib import Path

from app.services.image_validation import CONTENT_TYPE_EXTENSIONS

# vistiq-backend/ — computed from this file's location, same pattern as
# app/database/connection.py's DATA_DIR, so it's correct no matter which
# directory uvicorn is launched from.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOADS_DIR = BASE_DIR / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Mounted at this path in app/main.py — kept as one constant so the route
# that returns URLs and the mount that serves them can never drift apart.
UPLOADS_URL_PREFIX = "/uploads"


def save_clothing_image(raw_bytes: bytes, content_type: str) -> str:
    """Persists already-validated image bytes under a random, safe filename.
    Returns the servable relative URL, e.g. "/uploads/<uuid>.jpg" — the
    caller stores this string in ClothingItem.image; the frontend resolves
    it against the API base URL to render an <img>."""
    extension = CONTENT_TYPE_EXTENSIONS[content_type]
    filename = f"{uuid.uuid4().hex}{extension}"
    file_path = UPLOADS_DIR / filename
    file_path.write_bytes(raw_bytes)
    return f"{UPLOADS_URL_PREFIX}/{filename}"


def delete_clothing_image(image_url: str | None) -> None:
    """Best-effort cleanup of the local file backing a wardrobe item's photo
    (Stage 17), called when that item is deleted.

    Deliberately conservative — this must never turn a successful wardrobe
    delete into a failure, and must never delete anything it wasn't clearly
    asked to:
    - no-ops for None/empty, or any value that isn't one of our own
      "/uploads/<name>" URLs (e.g. a future external URL)
    - rejects any filename containing a path separator or "..", so it can
      never escape UPLOADS_DIR via a crafted value
    - re-checks the resolved path's parent is exactly UPLOADS_DIR before
      unlinking, as a second independent guard against path traversal
    - swallows OSError (already gone, permission issue, locked file, ...)
      rather than raising — the wardrobe record is already deleted by the
      time this runs, so a filesystem hiccup here must stay a no-op, not an
      error surfaced to the caller.
    """
    prefix = f"{UPLOADS_URL_PREFIX}/"
    if not image_url or not image_url.startswith(prefix):
        return

    filename = image_url[len(prefix):]
    if not filename or "/" in filename or "\\" in filename or filename in {".", ".."}:
        return

    file_path = UPLOADS_DIR / filename
    try:
        if file_path.is_file() and file_path.resolve().parent == UPLOADS_DIR.resolve():
            file_path.unlink()
    except OSError:
        pass
