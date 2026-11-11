"""Pydantic schemas for the virtual try-on API (Phase 5 — experimental)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

TRYON_STATUSES = ("pending", "processing", "completed", "failed")


class TryOnJobResponse(BaseModel):
    """What the API returns for a try-on job. `result_image`/`error_message`
    are populated only once the job reaches a terminal status."""

    id: int
    garment_item_id: int | None
    status: str
    result_image: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
