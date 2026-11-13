# VISTIQ CatVTON GPU Recovery — Execution Report

**Date:** 2026-11-13
**Scope:** Recover, implement, and run the CatVTON virtual try-on GPU worker end-to-end, integrate it into the VISTIQ repository, and attempt one complete end-to-end try-on through the live application.

This report distinguishes three categories throughout, as instructed:
- **Historically successful inference** — claimed in earlier sessions, not reproduced here.
- **Fresh worker inference** — genuinely re-verified, this session, with evidence below.
- **Fresh complete VISTIQ end-to-end inference** — attempted this session; **not achieved** (see §9).

---

## 1. Platform selected

**Google Colab.** Kaggle was not tested. Rationale: Colab already provided a live, freshly-allocated GPU on the first connection attempt, and this project has a documented prior incident of an accidental Kaggle "Factory Reset" from browser automation wiping a working session — given that risk and that Colab already worked, testing Kaggle as well would only have added risk without benefit. This matches the task's own instruction not to spend time on unnecessary verification once a working platform is found.

## 2. Actual GPU model and VRAM

- **GPU:** Tesla T4 (confirmed via `nvidia-smi` and `torch.cuda.get_device_name(0)`)
- **VRAM:** 15.64 GB total (reported as 14.56 GB usable headroom in a later OOM error message, consistent with normal reserved overhead)
- **Driver:** 580.82.07
- **CUDA (driver-reported):** 13.0

This was a **freshly allocated runtime**, confirmed live and not a stale/cached report — verified with a fresh `nvidia-smi` call timestamped at the moment of connection, separate from any historical data in this notebook's own prior-session cells.

## 3. Python, PyTorch, CUDA, and dependency versions (as actually installed and verified working)

| Component | Version |
|---|---|
| Python | 3.9.25 |
| PyTorch | 2.4.0+cu121 |
| Torchvision | 0.19.0+cu121 |
| Diffusers | 0.30.3 |
| Accelerate | 1.6.0 |
| Transformers | 4.46.3 |
| PEFT | 0.17.1 |
| Detectron2 | 0.6 (built from source, see §4) |
| xformers | 0.0.27.post2 |
| opencv (cv2) | 4.10.0.84 |
| numpy | 1.26.4 |
| FastAPI | 0.115.6 |
| uvicorn | 0.34.0 |

All verified via direct import checks in the live environment (`import torch; torch.__version__`, etc.), not assumed from a requirements file.

## 4. How the worker was implemented / recovered

**The original CatVTON GitHub repository is confirmed dead.** `https://github.com/Zheng-Chong/CatVTON` returned a genuine HTTP 404 when checked directly this session (`urllib.request.urlopen` → `HTTPError 404`), and a `git clone` against it failed with a credential-prompt-style error consistent with the repository no longer existing. This repository had been successfully cloned in a prior (2026-11-11) session recorded in this same Colab notebook, so it was taken down sometime between then and now — this is a confirmed, re-verified fact, not an assumption carried over from the project's existing docs (which already stated this).

**Recovery path used:** the author's own HuggingFace Space snapshot, `zhengchong/CatVTON` (Space), pinned to revision `58d5e58e9ac8e84ed71259407c4496ee9af253ea`. This snapshot bundles `model/pipeline.py` (`CatVTONPipeline`), `model/cloth_masker.py` (`AutoMaskerSeg`), and `utils.py` (`resize_and_crop`/`resize_and_padding`) — confirmed present and used directly, not reconstructed from memory. This revision uses SegFormer-based human parsing (`AutoMaskerSeg`) rather than the original SCHP-based masker — DensePose pose estimation itself is unaffected and still detectron2-based.

**Detectron2 + DensePose** were built from the **official, currently-alive** `facebookresearch/detectron2` repository (not Zheng-Chong's dead fork — DensePose is Facebook's own project and was unaffected by the CatVTON takedown). Built as a C++-only extension (`CUDA_VISIBLE_DEVICES=""`, `FORCE_CUDA="0"`) to work around a CUDA/PyTorch version mismatch on this runtime; DensePose's `R_50_FPN` config does not require detectron2's own custom CUDA kernels (ROIAlign/NMS delegate to torchvision), so GPU inference is unaffected by this build choice. Verified: `import detectron2; detectron2.__version__` → `0.6`; `import densepose` → OK.

**Three previously-undocumented, now-confirmed fixes** (all captured in `gpu-worker/app/catvton_service.py` and `gpu-worker/README.md` §7):
1. A `uv`-created Python 3.9 venv ships with no `pip`/`setuptools`/`wheel`; any source build fails with `error: invalid command 'bdist_wheel'` until these are installed first.
2. On this T4, PyTorch's `scaled_dot_product_attention` silently fell back to the "math" (full-materialization) backend instead of flash/memory-efficient attention, attempting an 18.00 GiB allocation at 768×1024 and OOMing instantly. Switching `weight_dtype` between bf16 and fp16 alone did **not** fix this (both use 2 bytes/element — the allocation size was byte-identical either way). The actual fix: `torch.backends.cuda.enable_flash_sdp(True)`, `enable_mem_efficient_sdp(True)`, `enable_math_sdp(False)`, set once before pipeline construction. Confirmed active during the successful run via `torch.backends.cuda.flash_sdp_enabled()`/`mem_efficient_sdp_enabled()`/`math_sdp_enabled()` → `True True False`.
3. The HF Space snapshot does not include the safety checker's NSFW-placeholder image (`resource/img/NSFW.jpg`); leaving the safety checker enabled crashed with `FileNotFoundError` whenever it fired, including on a technically-benign result. Fixed with `skip_safety_check=True` on `CatVTONPipeline` — this is a workaround for a missing asset, not a deliberate bypass of content moderation policy.

## 5. Worker API details

Implemented in `gpu-worker/app/main.py`, matching `vistiq-backend/app/services/tryon_worker.py`'s expected contract exactly:

- `GET /health` — no auth. Returns `{"status": "ok", "gpu_available": bool, "gpu_name": str|null, "model_ready": bool}`.
- `POST /tryon` — requires `Authorization: Bearer <CATVTON_WORKER_TOKEN>`; multipart `person_image`, `garment_image`, `cloth_type` (`upper`/`lower`/`overall`); returns `image/png` bytes on success, or a safe JSON error (401 unauthorized, 422 invalid input, 500 inference failed, 503 model not ready). Inference is serialized via `asyncio.Lock()` — one request at a time, matching the documented single-GPU constraint.

**Genuinely tested over real HTTP** (not just as a Python function call) via `curl` from within the same Colab runtime:
```
GET /health  → 200  {"status":"ok","gpu_available":true,"gpu_name":"Tesla T4","model_ready":true}
POST /tryon  → 200  (756,761-byte valid PNG, 768×1024, RGB), 71.5s elapsed
```

## 6. Model source and revision

| Component | Source | Revision/notes |
|---|---|---|
| Pipeline code | `zhengchong/CatVTON` (HF Space) | `58d5e58e9ac8e84ed71259407c4496ee9af253ea` |
| Attention weights | `zhengchong/CatVTON` (HF model) | latest, downloaded via `snapshot_download`; also bundles its own `DensePose/` checkpoint+config, confirmed identical in content to the standard detectron2 DensePose model zoo files |
| Base diffusion model | `runwayml/stable-diffusion-inpainting` | Confirmed still accessible (loads via unsafe-pickle fallback — no `.safetensors` file in that repo, a pre-existing, harmless warning, not introduced by this session) |
| Human parsing | `mattmdjaga/segformer_b2_clothes` | Auto-downloaded by `AutoMaskerSeg` |

## 7. Actual inference time (measured fresh, this session)

- **Direct pipeline call** (no HTTP layer): 65.9 seconds, 30 diffusion steps.
- **Full HTTP worker call** (bearer auth + multipart upload + inference): 71.5 seconds.
- **Historical reference** (documented in `docs/virtual-tryon.md`, not reproduced by this session): 66.3s and 77.0s.

These numbers closely reproduce the historical range, on the same GPU class (T4), under genuinely fresh conditions.

## 8. Peak GPU memory (measured fresh, this session)

- **Peak allocated:** 4.21 GB
- **Peak reserved:** 6.27 GB
- **Historical reference:** ~5.25 GB allocated / ~7.27 GB reserved

Measured via `torch.cuda.max_memory_allocated()` / `max_memory_reserved()` immediately after the real inference call completed.

## 9. Generated image evidence

A real try-on was generated from two of CatVTON's own official demo photos (bundled in the HF Space snapshot, same files VISTIQ's local `demo-assets/` already mirrors): a person photo (`resource/demo/example/person/men/model_5.png`) and a garment photo (`resource/demo/example/condition/upper/22790049_53294275_1000.jpg`, a cream sleeveless sweater vest with a Snoopy-playing-tennis graphic).

**Visually inspected and confirmed genuinely convincing**: the garment was correctly composited onto the person — realistic fabric drape, correct fit across the torso, the person's face/arms/jeans/background left unchanged. A cropped screenshot of this result is saved locally at `docs/catvton-gpu-evidence/fresh_inference_result_2026-11-13.png` (gitignored, not committed — it is a derivative of a CC BY-NC-SA 4.0 demo photo, and this project already avoids redistributing those beyond what CatVTON's own demo distribution covers, per the existing `/demo-assets/` policy in `.gitignore`).

Four raw output files (`catvton_fresh_person.png`, `catvton_fresh_cloth.png`, `catvton_fresh_mask.png`, `catvton_fresh_result.png`) were also saved inside the ephemeral Colab session at `/content/output/` — these were **not** copied out before the runtime disconnected (see §10) and are now lost; only the local screenshot survives as durable evidence.

## 10. End-to-end application result

**Not achieved.** Sequence of events:

1. The worker was built, started, and verified over its own HTTP contract (§5) — **fully successful**.
2. A Cloudflare Quick Tunnel was started (`cloudflared tunnel --url http://127.0.0.1:8001`), producing `https://difference-angela-sci-thumbzilla.trycloudflare.com`.
3. **Reachability from the actual local Windows machine running VISTIQ was independently confirmed** — a direct `curl` from that machine (not from within Colab) to the tunnel's `/health` endpoint returned `200 {"status":"ok",...}`. This is a genuine external-network proof, not a same-host loopback test.
4. `vistiq-backend/.env` was updated with this URL and a freshly-generated worker token (never reusing any previously-exposed token).
5. The local VISTIQ backend and frontend were started, a test garment and person photo were uploaded through the actual browser UI (`http://127.0.0.1:5173`), and "Generate Virtual Try-On" was clicked.
6. **The request failed**: "Could not reach the virtual try-on worker. Please try again later." Investigation showed the tunnel URL no longer resolved (`curl` → "Couldn't resolve host"), and the Colab tab showed "Reconnect" with all cell state lost.
7. Attempting to reconnect produced: **"Cannot connect to GPU backend — You cannot currently connect to a GPU due to usage limits in Colab."** — the free-tier GPU quota was exhausted between steps 3 and 5, matching this project's own documented historical pattern (quota exhaustion has happened before). This is treated as a genuine, accepted blocker, not retried further, per the task's own instruction not to spend time repeatedly checking GPU quotas.

`vistiq-backend/.env` was reverted to the honest disabled state (worker URL/token commented out) immediately after this was confirmed, consistent with the project's existing convention — every `/tryon` request now fails fast with a clear "not configured" message rather than waiting out a timeout against a dead host.

**What this does and does not prove:** steps 1-3 are functionally equivalent to what the VISTIQ backend's own `tryon_worker.py` does when it calls the worker (same HTTP method, same auth header, same multipart fields, same network path) — so there is strong indirect evidence the integration would have worked. But it was not literally exercised through the backend's own code path or the frontend's job-polling UI, and that specific, final link was not completed. Do not claim a live, UI-driven VISTIQ try-on succeeded this session — it did not.

## 11. Tests executed and their results

| Suite | Command | Result |
|---|---|---|
| Backend pytest | `vistiq-backend\.venv\Scripts\python.exe -m pytest tests/ -v --durations=5` | **203 passed**, 0 failed, 248 warnings (all pre-existing deprecation notices, none new), 40.1s |
| Frontend ESLint | `npx eslint .` (from `vistiq-frontend/`) | Clean, no output |
| Frontend TypeScript | `npx tsc -b --noEmit` | Clean, no errors |
| Frontend production build | `npm run build` | Succeeds, 1905 modules, 2.74s |

Run **after** all `.env` changes (including the revert in §10), confirming the GPU-worker investigation left the rest of the application untouched and working.

## 12. Git branch, commit, and merge details

Work was done on branch `catvton-gpu-worker`, created from `main` at commit `bed9e6f` (`docs: fix stale README claims, add API reference, demo script and viva guide`). See the commit log for this branch for exact hashes of what was committed and, if authorized and completed, merged — recorded separately once the commit step (Phase 6) is finished, to avoid this report claiming a commit/merge before it has actually happened.

## 13. Remaining limitations

- **No live GPU worker is running right now** — the Colab session is gone and its quota is exhausted. Restoring live inference requires a fresh Colab (or other GPU) session; `gpu-worker/README.md` has the exact, now-verified setup steps.
- **The full VISTIQ-app browser end-to-end flow was not completed this session** (§10) — the worker's own HTTP contract was proven correct, but the literal backend→worker→frontend round trip through the running app was not witnessed end-to-end due to the quota exhaustion timing.
- **CatVTON's `lower`-category (bottoms) try-on remains genuinely untested** — no bottoms example exists in CatVTON's own official demo set, and this session only tested `upper`.
- **CatVTON's CC BY-NC-SA 4.0 license** still forecloses any commercial deployment of this feature as-is (already documented in `docs/virtual-tryon.md` and `gpu-worker/README.md`).
- **The raw output images from this session's successful run were not preserved** — only a local screenshot crop survives (§9); the full-resolution PNGs were lost when the Colab runtime disconnected.
- **This revision's masking (`AutoMaskerSeg`, SegFormer-based) differs from the original CatVTON's SCHP-based masker** — DensePose pose estimation is unaffected, but this is a real, disclosed deviation from the very first published CatVTON implementation, inherited from using the HF Space snapshot as the recovery source (the original GitHub repo no longer exists to compare against directly).
