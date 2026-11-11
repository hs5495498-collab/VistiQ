# Virtual Try-On (Phase 5 — experimental)

## 1. What this is, and what it is not

VISTIQ's Virtual Try-On feature lets a user see one of their own wardrobe garments rendered onto a photo of themselves, using [CatVTON](https://github.com/Zheng-Chong/CatVTON) — a real diffusion-based virtual try-on research model, not a crude image composite.

**What's actually implemented and verified:**
- Genuine CatVTON inference was run and produced real, visually correct results (garment color/pattern correctly transferred, pose/background preserved) — see §4.
- The full VISTIQ job lifecycle: authenticated job creation, ownership-scoped status/result retrieval, deletion, and error handling — all automated-test-covered (`vistiq-backend/tests/test_tryon_api.py`).
- The React UI (`vistiq-frontend/src/pages/TryOn.tsx`): garment selection, photo upload, status polling, before/after comparison, history, honest unavailable/error states.

**What's explicitly NOT implemented:**
- A permanent, always-on GPU worker. VISTIQ's backend runs on a machine with no NVIDIA GPU (see `vistiq-backend/requirements.txt`'s CPU-only torch pin) and calls out to a separate worker over HTTP (`app/services/tryon_worker.py`) — but this repository does not ship or deploy that worker. The inference in §4 was run manually in a Google Colab notebook, which is a research/experimentation environment, not a production deployment target.
- With no worker configured (the default — `VISTIQ_TRYON_WORKER_URL` unset), every `POST /tryon` job is created for real, then immediately marked `failed` with a clear "unavailable" message — never silently stuck, never a fabricated success.

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
          - worker configured    -> calls it over HTTP (tryon_worker.py),
                                     stores the result or a safe failure message
  -> React polls GET /tryon/{id} every 2s until "completed"/"failed"
  -> GET /tryon/results/{filename} serves the result, ownership-checked
```

The "GPU worker" is any process that implements the HTTP contract documented in `app/services/tryon_worker.py`'s module docstring (`POST {url}/tryon`, multipart `person_image`+`garment_image`+`cloth_type`, returns `image/png` bytes or a JSON error). This repo does not implement or deploy one — see §1.

## 6. How to reproduce the Colab inference run

1. Open a fresh Colab notebook, select a GPU runtime (T4 is sufficient).
2. `git clone https://github.com/Zheng-Chong/CatVTON.git /content/CatVTON && cd /content/CatVTON && git checkout 7818397f25613beedb3d861a34769f607cfcf3b1`
3. Create an isolated Python 3.9 environment (`uv python install 3.9 && uv venv --python 3.9 /content/catvton-venv`).
4. Install `torch==2.4.0 torchvision==0.19.0` from the `cu121` PyTorch index, then every other pin in `requirements.txt` **except** swap `diffusers` for `diffusers==0.30.3` and `accelerate==0.31.0` for `accelerate==1.6.0` (see §3).
5. `from huggingface_hub import snapshot_download; snapshot_download(repo_id="zhengchong/CatVTON")` and `snapshot_download(repo_id="booksforcharlie/stable-diffusion-inpainting")` to fetch the checkpoints.
6. Construct `CatVTONPipeline` and `AutoMasker` exactly as `app.py` does (see that file for the exact constructor arguments), run on a sample pair from `resource/demo/example/`, save the result.

Do not attempt step 2 onward against a different CatVTON commit without re-verifying the dependency pins above — they were determined by actually hitting and diagnosing real failures at this specific commit, not read off the README.

## 7. Security

- Every `TryOnJob` row is scoped to `user_id`; every read/delete route filters by both `id` and `user_id` (see `app/routes/tryon.py`), identical to the existing wardrobe ownership pattern — a cross-user attempt and a genuinely nonexistent job both return a plain 404.
- Person photos and results are stored under dedicated, non-public directories (`data/tryon_person_images/`, `data/tryon_results/`) and served only through authenticated, ownership-checked routes — never a static file mount.
- Uploaded images go through the same validation as wardrobe photos (`app/services/image_validation.py`): content-type allowlist, 10MB size cap, must actually decode as an image.
- `POST /tryon` and `DELETE /tryon/{id}` require the CSRF header, identical to every other state-changing VISTIQ route.
- The worker call has a timeout (`VISTIQ_TRYON_WORKER_TIMEOUT_S`, default 120s) and every failure mode (not configured, unreachable, timeout, non-2xx, or an entirely unexpected exception) is caught and converted to a generic, safe `error_message` — a raw exception string, stack trace, or internal file path is never stored or returned to the client (verified by `test_unexpected_worker_exception_never_leaks_internal_details`).
- No model endpoint or Gradio UI is exposed publicly by this repository — see §1.

## 8. Current limitations

- No live GPU worker is deployed — see §1. The feature is fully built and tested up to that boundary; end-to-end real-inference-through-the-web-UI has **not** been verified, because there is nothing listening at a configured `VISTIQ_TRYON_WORKER_URL` in this project as shipped.
- Only two sample pairs have been qualitatively evaluated (§4) — no systematic accuracy/quality evaluation exists.
- CatVTON's own license restricts this to non-commercial use (§2).
- Only `upper`/`lower`/`overall` cloth types are supported (matching CatVTON's own categories) — Footwear and Accessories are excluded from the wardrobe picker in `TryOn.tsx`.
- No automated frontend test suite exists for `TryOn.tsx` (consistent with the rest of VISTIQ's frontend — see the root README's Testing section).
