"""CRUD endpoints for wardrobe (clothing item) records."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import ClothingItem
from app.schemas.clothing import (
    ClothingItemCreate,
    ClothingItemResponse,
    ClothingItemUpdate,
    ImageUploadResponse,
)
from app.services.image_storage import delete_clothing_image, save_clothing_image
from app.services.image_validation import read_and_validate_image

router = APIRouter(prefix="/wardrobe", tags=["wardrobe"])


def _get_item_or_404(item_id: int, db: Session) -> ClothingItem:
    item = db.get(ClothingItem, item_id)
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
)
def create_clothing_item(item: ClothingItemCreate, db: Session = Depends(get_db)):
    db_item = ClothingItem(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.get(
    "",
    response_model=list[ClothingItemResponse],
    summary="List all wardrobe items",
)
def list_clothing_items(db: Session = Depends(get_db)):
    return db.query(ClothingItem).order_by(ClothingItem.id).all()


@router.post(
    "/images",
    response_model=ImageUploadResponse,
    summary="Upload a wardrobe item photo, returning a servable image URL",
)
async def upload_wardrobe_image(file: UploadFile = File(...)):
    """Persists the file to local disk (app/services/image_storage.py) and
    returns its servable URL. Registered before /{item_id} below so the
    literal "/images" segment is matched first — FastAPI validates path
    params (item_id: int) only after route matching, so "/images" would
    otherwise wrongly try to match /{item_id} and 422 instead of reaching
    here. Deliberately separate from POST /wardrobe (which stays a plain
    JSON body): the frontend uploads the image first, then sends the
    returned URL as a normal string field in the JSON create/update call.
    """
    raw_bytes, _image = await read_and_validate_image(file)
    image_url = save_clothing_image(raw_bytes, file.content_type)
    return {"image": image_url}


@router.get(
    "/{item_id}",
    response_model=ClothingItemResponse,
    summary="Get a single wardrobe item by id",
)
def get_clothing_item(item_id: int, db: Session = Depends(get_db)):
    return _get_item_or_404(item_id, db)


@router.put(
    "/{item_id}",
    response_model=ClothingItemResponse,
    summary="Update a wardrobe item",
)
def update_clothing_item(
    item_id: int, item_update: ClothingItemUpdate, db: Session = Depends(get_db)
):
    db_item = _get_item_or_404(item_id, db)

    # Only overwrite fields the client actually included in the request body.
    updates = item_update.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(db_item, field, value)

    db.commit()
    db.refresh(db_item)
    return db_item


@router.delete(
    "/{item_id}",
    summary="Delete a wardrobe item",
)
def delete_clothing_item(item_id: int, db: Session = Depends(get_db)):
    db_item = _get_item_or_404(item_id, db)
    image_url = db_item.image

    db.delete(db_item)
    db.commit()

    # Runs only after the record is confirmed deleted, and never raises —
    # see delete_clothing_image()'s own docstring for why this is safe.
    delete_clothing_image(image_url)

    return {"message": f"Clothing item {item_id} deleted"}
