"""Response shape for GET /health. POST /tryon has no JSON request/response
schema -- it's multipart-in (person_image, garment_image, cloth_type) and
image/png-out -- so there's nothing to declare for it here.
"""
from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    gpu_available: bool
    gpu_name: Optional[str] = None
    model_ready: bool
