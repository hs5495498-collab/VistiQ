"""Unit tests for app/services/tryon_worker.py itself (Phase 5.2) — the
bearer-auth header it sends and the "not configured" logic. Unlike
test_tryon_api.py (which always mocks this module), these tests exercise
run_tryon()'s real HTTP-building logic, with httpx's own MockTransport
standing in for the network so no real worker is needed.
"""

import httpx
import pytest

from app.services import tryon_worker


@pytest.fixture(autouse=True)
def _clear_worker_env(monkeypatch):
    monkeypatch.delenv(tryon_worker.WORKER_URL_ENV_VAR, raising=False)
    monkeypatch.delenv(tryon_worker.WORKER_TOKEN_ENV_VAR, raising=False)
    monkeypatch.delenv(tryon_worker.WORKER_TIMEOUT_ENV_VAR, raising=False)


def test_not_configured_when_url_and_token_both_missing():
    assert tryon_worker.is_worker_configured() is False


def test_not_configured_when_token_missing(monkeypatch):
    monkeypatch.setenv(tryon_worker.WORKER_URL_ENV_VAR, "https://worker.example.test")
    assert tryon_worker.is_worker_configured() is False


def test_not_configured_when_url_missing(monkeypatch):
    monkeypatch.setenv(tryon_worker.WORKER_TOKEN_ENV_VAR, "secret-token")
    assert tryon_worker.is_worker_configured() is False


def test_configured_when_both_present(monkeypatch):
    monkeypatch.setenv(tryon_worker.WORKER_URL_ENV_VAR, "https://worker.example.test")
    monkeypatch.setenv(tryon_worker.WORKER_TOKEN_ENV_VAR, "secret-token")
    assert tryon_worker.is_worker_configured() is True


def test_run_tryon_raises_honest_unavailable_when_not_configured():
    with pytest.raises(tryon_worker.TryOnWorkerError, match="no GPU worker is configured"):
        tryon_worker.run_tryon(b"person", "image/png", b"garment", "image/png", "upper")


def test_run_tryon_sends_bearer_token_and_returns_png_bytes(monkeypatch):
    monkeypatch.setenv(tryon_worker.WORKER_URL_ENV_VAR, "https://worker.example.test")
    monkeypatch.setenv(tryon_worker.WORKER_TOKEN_ENV_VAR, "secret-token")

    seen_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, content=b"fake-png-bytes", headers={"content-type": "image/png"})

    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Client(transport=httpx.MockTransport(handler)).post(*a, **k))

    result = tryon_worker.run_tryon(b"person", "image/png", b"garment", "image/png", "upper")

    assert result == b"fake-png-bytes"
    assert len(seen_requests) == 1
    assert seen_requests[0].headers["authorization"] == "Bearer secret-token"
    assert seen_requests[0].url == "https://worker.example.test/tryon"


def test_run_tryon_raises_safe_error_on_401(monkeypatch):
    monkeypatch.setenv(tryon_worker.WORKER_URL_ENV_VAR, "https://worker.example.test")
    monkeypatch.setenv(tryon_worker.WORKER_TOKEN_ENV_VAR, "wrong-token")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Unauthorized."})

    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Client(transport=httpx.MockTransport(handler)).post(*a, **k))

    with pytest.raises(tryon_worker.TryOnWorkerError, match="could not process this request"):
        tryon_worker.run_tryon(b"person", "image/png", b"garment", "image/png", "upper")
