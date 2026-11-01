"""Shared upload validation for every endpoint that accepts an image file
(POST /analyze-clothing, POST /wardrobe/images). Keeping this in one place
guarantees both endpoints reject the same bad input the same way instead of
silently drifting apart.
"""

from io import BytesIO

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# Extension is derived from the validated content-type — never from the
# client-supplied filename, which is untrusted.
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


async def read_and_validate_image(file: UploadFile) -> tuple[bytes, Image.Image]:
    """Validates content-type, size, and that the bytes are actually a
    decodable image. Returns (raw_bytes, opened_image). Raises HTTPException
    (415/400/413) on any failure — callers don't need their own checks."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{file.content_type}'. Upload a JPEG, PNG, or WEBP image.",
        )

    raw_bytes = await file.read()

    if not raw_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image is too large. Maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)}MB.",
        )

    try:
        image = Image.open(BytesIO(raw_bytes))
        image.load()  # decode now, inside the try, instead of failing lazily later
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read this file as an image. Upload a valid JPEG, PNG, or WEBP image.",
        )

    return raw_bytes, image
