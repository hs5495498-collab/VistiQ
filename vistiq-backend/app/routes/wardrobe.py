"""CRUD endpoints for wardrobe (clothing item) records — Phase 4:
every route below is now scoped to the authenticated user.

Ownership rule, enforced the same way everywhere: every query that reads,
updates, or deletes a specific item filters by BOTH `id` AND
`user_id == current_user.id` in one query. A cross-user access attempt
(an id that exists but belongs to someone else) and a genuinely
nonexistent id are therefore indistinguishable — both produce a plain 404
— so the API never confirms that a private item exists for a user who
doesn't own it. The authenticated server-side user (never a user id taken
from the request body) is always what determines ownership.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ClothingItem, User
from app.schemas.clothing import (
    ClothingItemCreate,
    ClothingItemResponse,
    ClothingItemUpdate,
    ImageUploadResponse,
)
from app.security.dependencies import get_current_user, require_csrf
from app.services import image_storage
from app.services.image_storage import UPLOADS_URL_PREFIX, delete_clothing_image, save_clothing_image
from app.services.image_validation import read_and_validate_image

router = APIRouter(prefix="/wardrobe", tags=["wardrobe"])


def _get_owned_item_or_404(item_id: int, user_id: int, db: Session) -> ClothingItem:
    item = db.query(ClothingItem).filter(ClothingItem.id == item_id, ClothingItem.user_id == user_id).first()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clothing item {item_id} not found",
        )
    return item


@router.post(
    "",
    response_model=ClothingItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new wardrobe item",
    dependencies=[Depends(require_csrf)],
)
def create_clothing_item(
    item: ClothingItemCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    db_item = ClothingItem(**item.model_dump(), user_id=current_user.id)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.get(
    "",
    response_model=list[ClothingItemResponse],
    summary="List the authenticated user's wardrobe items",
)
def list_clothing_items(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(ClothingItem)
        .filter(ClothingItem.user_id == current_user.id)
        .order_by(ClothingItem.id)
        .all()
    )


@router.post(
    "/images",
    response_model=ImageUploadResponse,
    summary="Upload a wardrobe item photo, returning a servable image URL",
    dependencies=[Depends(require_csrf)],
)
async def upload_wardrobe_image(file: UploadFile = File(...), _current_user: User = Depends(get_current_user)):
    """Persists the file to local disk (app/services/image_storage.py) and
    returns its servable URL — now under /wardrobe/images/<filename>,
    served by get_wardrobe_image() below (ownership-checked), not a public
    static mount. Requires authentication (so an anonymous client can't
    fill the disk with uploads) even though the file isn't yet linked to
    a specific item — see that function's docstring for why a brief
    unlinked-but-authenticated window is harmless.
    """
    raw_bytes, _image = await read_and_validate_image(file)
    image_url = save_clothing_image(raw_bytes, file.content_type)
    return {"image": image_url}


@router.get(
    "/images/{filename}",
    summary="Serve a wardrobe photo — only to the user who owns the item it's attached to",
)
def get_wardrobe_image(
    filename: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Replaces the old public `StaticFiles` mount (removed from
    app/main.py). Ownership is checked by looking up whether ANY of the
    current user's items actually reference this exact filename — a
    filename that exists on disk but isn't (yet, or ever) attached to one
    of the caller's own items returns 404, identical to a filename that
    doesn't exist at all. Never reveals which case it was.
    """
    if not filename or "/" in filename or "\\" in filename or filename in {".", ".."}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")

    image_url = f"{UPLOADS_URL_PREFIX}/{filename}"
    owned = (
        db.query(ClothingItem)
        .filter(ClothingItem.image == image_url, ClothingItem.user_id == current_user.id)
        .first()
    )
    if owned is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")

    file_path = image_storage.UPLOADS_DIR / filename
    if not file_path.is_file() or file_path.resolve().parent != image_storage.UPLOADS_DIR.resolve():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")

    return FileResponse(file_path)


@router.get(
    "/{item_id}",
    response_model=ClothingItemResponse,
    summary="Get a single wardrobe item by id (only if it belongs to the authenticated user)",
)
def get_clothing_item(
    item_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return _get_owned_item_or_404(item_id, current_user.id, db)


@router.put(
    "/{item_id}",
    response_model=ClothingItemResponse,
    summary="Update a wardrobe item (only if it belongs to the authenticated user)",
    dependencies=[Depends(require_csrf)],
)
def update_clothing_item(
    item_id: int,
    item_update: ClothingItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_item = _get_owned_item_or_404(item_id, current_user.id, db)

    # Only overwrite fields the client actually included in the request body.
    updates = item_update.model_dump(exclude_unset=True)

    # Image replacement (Phase 1): if this update is actually changing the
    # photo, remember the OLD image so it can be deleted only after the
    # new value is safely committed — never before, so a failed commit
    # leaves the existing (still-valid) image completely untouched.
    replacing_image = "image" in updates and updates["image"] != db_item.image
    old_image = db_item.image if replacing_image else None

    for field, value in updates.items():
        setattr(db_item, field, value)

    db.commit()
    db.refresh(db_item)

    if replacing_image:
        # Only reached after a successful commit. Best-effort (never raises)
        # — see delete_clothing_image()'s own docstring.
        delete_clothing_image(old_image)

    return db_item


@router.delete(
    "/{item_id}",
    summary="Delete a wardrobe item (only if it belongs to the authenticated user)",
    dependencies=[Depends(require_csrf)],
)
def delete_clothing_item(
    item_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    db_item = _get_owned_item_or_404(item_id, current_user.id, db)
    image_url = db_item.image

    db.delete(db_item)
    db.commit()

    # Runs only after the record is confirmed deleted, and never raises —
    # see delete_clothing_image()'s own docstring for why this is safe.
    delete_clothing_image(image_url)

    return {"message": f"Clothing item {item_id} deleted"}
