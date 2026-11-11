# Virtual Try-On (Phase 5 — experimental)

## 1. What this is, and what it is not

VISTIQ's Virtual Try-On feature lets a user see one of their own wardrobe garments rendered onto a photo of themselves, using [CatVTON](https://github.com/Zheng-Chong/CatVTON) — a real diffusion-based virtual try-on research model, not a crude image composite.

**What's actually implemented and verified:**
- Genuine CatVTON inference was run and produced real, visually correct results (garment color/pattern correctly transferred, pose/background preserved) — see §4.
- The full VISTIQ job lifecycle: authenticated job creation, ownership-scoped status/result retrieval, deletion, and error handling — all automated-test-covered (`vistiq-backend/tests/test_tryon_api.py`, `test_tryon_worker.py`).
- The React UI (`vistiq-frontend/src/pages/TryOn.tsx`): garment selection, photo upload, status polling, before/after comparison, history, honest unavailable/error states.
- **Phase 5.2**: the backend was connected to a genuinely running GPU worker (in Google Colab, exposed over a temporary authenticated HTTPS tunnel) and driven end-to-end through the real browser UI — see §9.

**What's explicitly NOT implemented:**
- A permanent, always-on GPU worker. VISTIQ's backend runs on a machine with no NVIDIA GPU (see `vistiq-backend/requirements.txt`'s CPU-only torch pin) and calls out to a separate worker over HTTP (`app/services/tryon_worker.py`) — this repository does not ship or deploy that worker; §9 documents how to stand one up temporarily in Colab for manual testing, which is a research/experimentation environment, not a production deployment target.
- With no worker configured — either `VISTIQ_TRYON_WORKER_URL` or `VISTIQ_TRYON_WORKER_TOKEN` unset/empty (the default) — every `POST /tryon` job is created for real, then immediately marked `failed` with a clear "unavailable" message — never silently stuck, never a fabricated success.

## 2. License and provenance — why this is a research feature, not a product feature yet

| Component | Source | License | Restriction |
|---|---|---|---|
| CatVTON attention weights, SCHP, DensePose checkpoints | [`zhengchong/CatVTON`](https://huggingface.co/zhengchong/CatVTON) on Hugging Face | **CC BY-NC-SA 4.0** | **Non-commercial use only**, share-alike, attribution required |
| CatVTON source code | [`Zheng-Chong/CatVTON`](https://github.com/Zheng-Chong/CatVTON), commit `7818397f25613beedb3d861a34769f607cfcf3b1` | Repository's own LICENSE (CC BY-NC-SA 4.0, matching the weights) | Non-commercial |
| Base inpainting diffusion model | [`booksforcharlie/stable-diffusion-inpainting`](https://huggingface.co/booksforcharlie/stable-diffusion-inpainting) (a re-upload of the original RunwayML checkpoint, which was taken down) | CreativeML OpenRAIL-M | Use-based restrictions (no illegal/harmful use), broader than NC but not unrestricted |
| Detectron2 / DensePose (human parsing dependency) | Vendored inside the CatVTON repo, precompiled for Python 3.9 | Apache 2.0 (detectron2) | — |

**Because the CatVTON weights themselves are CC BY-NC-SA 4.0, this feature is a private research proof of concept.** It must not be deployed as part of a commercial product, and VISTIQ's own CatVTON-derived code/outputs must preserve attribution and remain under compatible terms if ever redistributed. If VISTIQ needs a commercially-usable virtual try-on model in the future, that requires either a differently-licensed model or a commercial license from the CatVTON authors — out of scope for this phase.

CatVTON's own upstream repository has had no commits since December 2025 (verified via its GitHub API `pushed_at` field) — treat it as effectively frozen, not actively maintained.

## 3. Environment that actually worked (verified, reproducible)

This is the exact combination that was installed and tested — not a recommendation guessed from documentation:

| Package | Version |
|---|---|
| Python | 3.9.25 |
| PyTorch | 2.4.0+cu121 |
| Torchvision | 0.19.0+cu121 |
| Diffusers | **0.30.3** (NOT the repo's own `requirements.txt` pin of `git+https://github.com/huggingface/diffusers.git` — that resolves to a dev snapshot requiring Python ≥3.11 and breaks on Python 3.9; 0.30.3 is the latest release still declaring `python_requires >= 3.8` and was verified to contain every API CatVTON's code imports) |
| Transformers | 4.46.3 |
| Accelerate | **1.6.0** (NOT the repo's pin of `0.31.0` — `peft`'s `loftq_utils.py` imports `accelerate.utils.memory.clear_device_cache`, which doesn't exist until a later accelerate release; 1.6.0 is the first checked release that both defines it and still supports Python 3.9) |
| PEFT | 0.17.1 |
| Detectron2 | 0.6 (the repo's own vendored, precompiled-for-Python-3.9 binary — reused as-is, never rebuilt) |
| GPU | Tesla T4 (Google Colab), 15.64 GB VRAM |

**Why the two deviations from CatVTON's own `requirements.txt` were necessary and safe:** both are documented, verified-compatible substitutions for pins that are either unpinned-to-a-moving-target (diffusers) or simply missing a function the installed PEFT version needs (accelerate) — not arbitrary version bumps. See the commit history / PR discussion in this project's own development notes for the step-by-step diagnosis.

## 4. Genuine inference results (not simulated, not described secondhand)

Two independent sample pairs from CatVTON's own official demo images (`resource/demo/example/`) were run through the real pipeline (`model.pipeline.CatVTONPipeline` + `model.cloth_masker.AutoMasker`), fp16, 30 diffusion steps, 768×1024 working resolution, seeded for reproducibility.

| Run | Garment type | Person image | Inference time | Peak VRAM (allocated / reserved) |
|---|---|---|---|---|
| 1 | `upper` (grey cardigan, green trim) | male model, 960×1280 original | 66.3 s | 5.25 GB / 7.27 GB |
| 2 | `overall` (floral dress) | female model, 768×1024 original | 77.0 s | 5.25 GB / 7.27 GB |

Both comfortably fit the T4's 15.64 GB VRAM budget. Qualitatively: garment color and pattern were transferred accurately in both runs, the person's pose/face/background/legs were preserved, and no major artifacts were visible in either result at a normal viewing size. This is two samples, not a systematic evaluation — no SSIM/FID/LPYIPS or other quantitative metric was computed or is claimed.

## 5. Architecture

```
React TryOn.tsx
  -> POST /tryon (multipart: garment_item_id, cloth_type, person_image)
     -> FastAPI validates ownership/input, saves the person photo,
        creates a TryOnJob row (status "pending"), returns immediately
     -> BackgroundTask (app/routes/tryon.py:_process_job) runs after
        the response is sent:
          - no worker configured -> marks "failed" immediately, safe message
          - worker configured    -> calls it over HTTP + Bearer auth
                                     (tryon_worker.py), stores the result
                                     or a safe failure message
  -> React polls GET /tryon/{id} every 2s until "completed"/"failed"
  -> GET /tryon/results/{filename} serves the result, ownership-checked
```

The "GPU worker" is any process that implements the HTTP contract documented in `app/services/tryon_worker.py`'s module docstring (`POST {url}/tryon`, `Authorization: Bearer <token>`, multipart `person_image`+`garment_image`+`cloth_type`, returns `image/png` bytes or a JSON error). This repo does not implement or deploy one as a standing service — §9 documents the worker script used to stand one up temporarily in Colab.

## 6. How to reproduce the Colab inference run

1. Open a fresh Colab notebook, select a GPU runtime (T4 is sufficient).
2. `git clone https://github.com/Zheng-Chong/CatVTON.git /content/CatVTON && cd /content/CatVTON && git checkout 7818397f25613beedb3d861a34769f607cfcf3b1`
3. Create an isolated Python 3.9 environment (`uv python install 3.9 && uv venv --python 3.9 /content/catvton-venv`).
4. Install `torch==2.4.0 torchvision==0.19.0` from the `cu121` PyTorch index, then every other pin in `requirements.txt` **except** swap `diffusers` for `diffusers==0.30.3` and `accelerate==0.31.0` for `accelerate==1.6.0` (see §3).
5. `from huggingface_hub import snapshot_download; snapshot_download(repo_id="zhengchong/CatVTON")` and `snapshot_download(repo_id="booksforcharlie/stable-diffusion-inpainting")` to fetch the checkpoints.
6. Construct `CatVTONPipeline` and `AutoMasker` exactly as `app.py` does (see that file for the exact constructor arguments), run on a sample pair from `resource/demo/example/`, save the result.

Do not attempt step 2 onward against a different CatVTON commit without re-verifying the dependency pins above — they were determined by actually hitting and diagnosing real failures at this specific commit, not read off the README.

## 7. Security

- Every `TryOnJob` row is scoped to `user_id`; every read/delete route filters by both `id` and `user_id` (see `app/routes/tryon.py`), identical to the existing wardrobe ownership pattern — a cross-user attempt and a genuinely nonexistent job both return a plain 404 (verified manually with two real browser accounts, §9).
- Person photos and results are stored under dedicated, non-public directories (`data/tryon_person_images/`, `data/tryon_results/`) and served only through authenticated, ownership-checked routes — never a static file mount.
- Uploaded images go through the same validation as wardrobe photos (`app/services/image_validation.py`): content-type allowlist, 10MB size cap, must actually decode as an image.
- `POST /tryon` and `DELETE /tryon/{id}` require the CSRF header, identical to every other state-changing VISTIQ route.
- The worker call has a timeout (`VISTIQ_TRYON_WORKER_TIMEOUT_S`, default 120s, 180s recommended for Colab's GPU warm-up variance) and every failure mode (not configured, unreachable, timeout, non-2xx, or an entirely unexpected exception) is caught and converted to a generic, safe `error_message` — a raw exception string, stack trace, or internal file path is never stored or returned to the client (verified by `test_unexpected_worker_exception_never_leaks_internal_details`).
- The worker itself requires a bearer token (`VISTIQ_TRYON_WORKER_TOKEN` on the VISTIQ side, `CATVTON_WORKER_TOKEN` on the worker side — same value, generated once, never committed) on every `/tryon` request; a request with a missing or incorrect token gets a plain 401 from the worker, which VISTIQ's own worker client converts to the same safe `error_message` as any other failure. The token is read from the environment on both sides and is never logged, printed, committed, or sent to the browser.
- No model endpoint or Gradio UI is exposed publicly by this repository — see §1.

## 8. Current limitations

- No *permanent* GPU worker is deployed — see §1 and §9. §9's worker is temporary (tied to one Colab session) and was used for manual/verification purposes only, not a production deployment.
- Only two sample pairs have been qualitatively evaluated for visual/photorealistic quality (§4) — no systematic accuracy/quality evaluation exists. The Phase 5.2 end-to-end browser verification (§9) used synthetic placeholder images (solid-color rectangles) to exercise the plumbing (auth, job lifecycle, storage, UI polling) — CatVTON's person-detection step finds no human figure in those, so that run's output image is not evidence of garment-transfer quality; §4's two demo-photo runs remain the only quality evidence.
- CatVTON's own license restricts this to non-commercial use (§2).
- Only `upper`/`lower`/`overall` cloth types are supported (matching CatVTON's own categories) — Footwear and Accessories are excluded from the wardrobe picker in `TryOn.tsx`.
- No automated frontend test suite exists for `TryOn.tsx` (consistent with the rest of VISTIQ's frontend — see the root README's Testing section).

## 9. Live worker connection over a temporary tunnel (Phase 5.2)

This section documents a worker that was actually run and connected to VISTIQ's real backend and driven through the real browser UI — not a description of a theoretical setup.

**Worker script** (`_catvton_worker.py`, run inside the Colab notebook, never committed to this repo): a small FastAPI app built directly on the same `CatVTONPipeline`/`AutoMasker` construction as the Colab verification script in §6, with:
- `GET /health` — no auth required, reports `{status, gpu_available, gpu_name, model_ready}`.
- `POST /tryon` — requires `Authorization: Bearer <CATVTON_WORKER_TOKEN>`; missing/incorrect token → 401; otherwise validates `cloth_type`, runs real inference under an `asyncio.Lock()` (one request at a time — a single T4 cannot usefully serve concurrent diffusion runs), and returns the PNG or a safe 500/503 on failure.
- The token is read once from `CATVTON_WORKER_TOKEN` at process start; it is generated once, copied by hand between the Colab environment and the local `.env` (never typed or printed by an automated agent), and compared between the two sides only via independently-computed SHA-256 hashes — the raw value itself is never displayed in any terminal, notebook cell, or log.

**Exposing it**: a [Cloudflare Quick Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/) (`cloudflared tunnel --url http://127.0.0.1:8001 --no-autoupdate`) gives a temporary `https://<random-words>.trycloudflare.com` URL with no Cloudflare account needed. This is a convenience tunnel, not a stable endpoint — it lasts only as long as the Colab session and the `cloudflared` process stay up, and a new run gets a new URL.

**Connecting VISTIQ**: three environment variables in `vistiq-backend/.env` (loaded at process start via `python-dotenv`, see `app/main.py`):

```
VISTIQ_TRYON_WORKER_URL=https://<the tunnel's current URL>
VISTIQ_TRYON_WORKER_TOKEN=<the same value as the worker's CATVTON_WORKER_TOKEN>
VISTIQ_TRYON_WORKER_TIMEOUT_S=180
```

`app/services/tryon_worker.py` treats the worker as "configured" only when **both** the URL and the token are set (see `is_worker_configured()`) — a URL with no token would otherwise just produce a confusing generic failure instead of the honest "unavailable" message.

**What was verified with this setup, genuinely, not simulated:**
- `/health` reachable through the tunnel from an external machine (not just Colab's own loopback): `{"status":"ok","gpu_available":true,"gpu_name":"Tesla T4","model_ready":true}`.
- Missing and incorrect bearer tokens both rejected with 401, through the tunnel, with real multipart payloads (not just a bodyless request that would 422 before ever reaching the auth check).
- Two real inference requests through the tunnel from an external client completed in 66–68 seconds each, returning valid 768×1024 PNGs — consistent with the §4 loopback timings (the tunnel itself adds negligible overhead).
- A real request through VISTIQ's own backend (`POST /tryon` → background task → `tryon_worker.run_tryon()` → the live tunnel) completed with the job reaching `status: "completed"`, a result image saved by `tryon_storage` and served back through the ownership-checked `/tryon/results/{filename}` route, and GPU memory around 7 GB used on the T4 — all through the real FastAPI app, not a mocked `tryon_worker`.
- A full browser session, logged in as a real VISTIQ user: selecting a wardrobe garment, uploading a photo, submitting, watching the UI poll from "processing" to "completed", and seeing the before/after result and updated history render in the actual page — then refreshing the page (the completed job and its thumbnail remained retrievable) and deleting the job (its DB row and both image files were removed).
- Two-account isolation: a second real account's `GET /tryon/{id}` and `GET /tryon/results/{filename}` for the first account's job both returned a plain 404 (not 403 — ownership checks never reveal that a resource exists for someone else), and the second account's own history correctly showed no try-on attempts.

**Limitations specific to this setup**: it is tied to one interactive Colab session — if that notebook's runtime disconnects (Colab recycles idle runtimes), the tunnel and worker both go down, `VISTIQ_TRYON_WORKER_URL` starts pointing at nothing, and every new job falls back to the honest "unavailable" `failed` state already described in §1 (this fallback itself is automated-test-covered and does not depend on a worker actually being reachable). Reconnecting requires rerunning the Colab setup (§6) and updating `.env` with the new tunnel URL.
