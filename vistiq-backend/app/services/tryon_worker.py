"""Client for the separate GPU inference worker that actually runs CatVTON
(Phase 5 — experimental).

Why a separate worker at all: the machine this FastAPI backend runs on has
no NVIDIA GPU (see requirements.txt's CPU-only torch pin), and CatVTON's
own license (CC BY-NC-SA 4.0 on the fine-tuned weights — see
docs/virtual-tryon.md) restricts this to non-commercial research use. This
module never runs CatVTON itself; it only calls out to wherever it IS
running, over HTTP.

Configuration is a single env var, read fresh on every call (so tests can
monkeypatch os.environ without reloading this module):

    VISTIQ_TRYON_WORKER_URL — base URL of a running worker (e.g. an ngrok/
    Cloud Tunnel URL pointing at a Colab notebook, or a real GPU server).
    Unset/empty (the default) means no worker is connected at all — see
    `is_worker_configured()`. This project does NOT ship a live worker;
    wiring one up is a deployment-time decision, never hardcoded here.

Expected worker contract (not implemented by this repo — the worker is
whatever process is pointed at by the URL above):

    POST {WORKER_URL}/tryon
    multipart/form-data:
      person_image: file
      garment_image: file
      cloth_type: "upper" | "lower" | "overall"
    200 OK, body: image/png bytes (the generated result)
    4xx/5xx: JSON {"detail": "<safe, human-readable message>"}
"""

import os

import httpx

WORKER_URL_ENV_VAR = "VISTIQ_TRYON_WORKER_URL"
WORKER_TIMEOUT_ENV_VAR = "VISTIQ_TRYON_WORKER_TIMEOUT_S"
DEFAULT_TIMEOUT_S = 120.0


class TryOnWorkerError(Exception):
    """Raised for every failure mode below (not configured, unreachable,
    timed out, or the worker itself returned an error) — callers
    (app/routes/tryon.py) catch this one type and store `str(exc)` as
    TryOnJob.error_message, which is why every message raised here must
    already be safe to show a user (no stack traces, no internal paths)."""


def is_worker_configured() -> bool:
    return bool(os.environ.get(WORKER_URL_ENV_VAR, "").strip())


def _worker_url() -> str:
    return os.environ.get(WORKER_URL_ENV_VAR, "").strip().rstrip("/")


def _timeout_seconds() -> float:
    raw = os.environ.get(WORKER_TIMEOUT_ENV_VAR, "").strip()
    try:
        return float(raw) if raw else DEFAULT_TIMEOUT_S
    except ValueError:
        return DEFAULT_TIMEOUT_S


def run_tryon(
    person_bytes: bytes,
    person_content_type: str,
    garment_bytes: bytes,
    garment_content_type: str,
    cloth_type: str,
) -> bytes:
    """Synchronous call to the configured worker. Returns the raw PNG bytes
    of the generated result on success. Raises TryOnWorkerError (safe
    message only) for every failure mode — not configured, connection
    refused, timeout, or a non-2xx response."""
    if not is_worker_configured():
        raise TryOnWorkerError(
            "Virtual try-on is currently unavailable: no GPU worker is configured."
        )

    url = f"{_worker_url()}/tryon"
    files = {
        "person_image": ("person.png", person_bytes, person_content_type),
        "garment_image": ("garment.png", garment_bytes, garment_content_type),
    }
    try:
        response = httpx.post(url, files=files, data={"cloth_type": cloth_type}, timeout=_timeout_seconds())
    except httpx.TimeoutException:
        raise TryOnWorkerError("The virtual try-on worker took too long to respond. Please try again.")
    except httpx.RequestError:
        raise TryOnWorkerError("Could not reach the virtual try-on worker. Please try again later.")

    if response.status_code != 200:
        raise TryOnWorkerError("The virtual try-on worker could not process this request.")

    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise TryOnWorkerError("The virtual try-on worker returned an unexpected response.")

    return response.content
