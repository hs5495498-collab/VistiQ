"""VISTIQ CatVTON GPU worker -- FastAPI app.

Run this on a machine/notebook with an NVIDIA GPU, in its own Python 3.9
virtual environment (see ../README.md for the exact, verified setup).
Never run this inside vistiq-backend's own CPU-only venv.

HTTP contract (matches app/services/tryon_worker.py on the main backend):
    GET  /health  -- no auth, {status, gpu_available, gpu_name, model_ready}
    POST /tryon   -- Authorization: Bearer <CATVTON_WORKER_TOKEN>,
                     multipart person_image + garment_image + cloth_type
                     ("upper" | "lower" | "overall"), returns image/png or
                     a safe JSON error (401/422/500/503).
"""
import asyncio
import io
import os
from typing import Optional

import torch
from fastapi import FastAPI, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image

from app.catvton_service import CatVTONService
from app.schemas import HealthResponse

WORKER_TOKEN = os.environ.get("CATVTON_WORKER_TOKEN", "")

app = FastAPI(title="VISTIQ CatVTON GPU worker")
_lock = asyncio.Lock()
_service: Optional[CatVTONService] = None


@app.on_event("startup")
def _load_model() -> None:
    global _service
    _service = CatVTONService()


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        gpu_available=torch.cuda.is_available(),
        gpu_name=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        model_ready=_service is not None,
    )


@app.post("/tryon")
async def tryon(
    authorization: str = Header(None),
    person_image: UploadFile = None,
    garment_image: UploadFile = None,
    cloth_type: str = Form("upper"),
):
    if not WORKER_TOKEN or authorization != f"Bearer {WORKER_TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")
    if cloth_type not in ("upper", "lower", "overall"):
        raise HTTPException(status_code=422, detail="invalid cloth_type")
    if _service is None:
        raise HTTPException(status_code=503, detail="model not ready")
    if person_image is None or garment_image is None:
        raise HTTPException(status_code=422, detail="person_image and garment_image are required")

    person_bytes = await person_image.read()
    garment_bytes = await garment_image.read()

    async with _lock:  # a single GPU can't usefully serve concurrent diffusion runs
        try:
            person = Image.open(io.BytesIO(person_bytes)).convert("RGB")
            garment = Image.open(io.BytesIO(garment_bytes)).convert("RGB")
            result = _service.run(person, garment, cloth_type)
            buf = io.BytesIO()
            result.save(buf, format="PNG")
            return Response(content=buf.getvalue(), media_type="image/png")
        except HTTPException:
            raise
        except Exception as exc:  # never leak internals to the client
            print("INFERENCE_ERROR", repr(exc), flush=True)
            raise HTTPException(status_code=500, detail="inference_failed")


# Run with: python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
# (from the gpu-worker/ directory -- see README.md). Not run as a plain
# script (`python app/main.py`): the `from app....` imports above need
# gpu-worker/ itself on sys.path, which only the module-style invocation
# (`-m` / the uvicorn CLI) guarantees.
