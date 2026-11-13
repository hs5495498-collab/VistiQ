# VISTIQ — CatVTON GPU Worker Setup

Procedural setup guide for standing up a CatVTON GPU worker. For the full evidence, license analysis, and verified inference results behind this feature, see `docs/virtual-tryon.md` — this document is deliberately just the steps.

## Current status (as of 2026-11-13, updated same day)

**No GPU worker is currently running**, but a packaged, working implementation now exists at `gpu-worker/` (full setup in `gpu-worker/README.md`) that was built and genuinely verified live this same day: real CatVTON inference, matching historical timing/VRAM figures almost exactly, over the actual worker HTTP contract (`curl`-tested, `200 OK`, valid PNG). Colab's free-tier GPU quota was then exhausted mid-session, before a full VISTIQ-app browser end-to-end test could run — see `docs/CATVTON_GPU_EXECUTION_REPORT.md` for the complete, evidence-based account of what was and wasn't achieved. The steps below (and the more detailed, copy-pasteable version in `gpu-worker/README.md`) describe how to stand the worker back up once GPU access is available again. With no worker configured, VISTIQ's Virtual Try-On feature already handles this honestly — every job fails immediately with a clear "unavailable" message (see `docs/KNOWN_LIMITATIONS.md`) rather than hanging.

**Three real fixes discovered and confirmed this session**, beyond what's documented below (all already applied in `gpu-worker/app/catvton_service.py`):
1. A uv-created Python 3.9 venv ships with no `pip`/`setuptools`/`wheel`, so any source build (detectron2) fails with `error: invalid command 'bdist_wheel'` until those are installed first.
2. On a T4-class GPU, PyTorch's SDPA can silently fall back to the "math" (full-materialization) attention backend instead of flash/memory-efficient attention, which tries to allocate ~18GB and OOMs instantly at 768×1024. Fix: `torch.backends.cuda.enable_flash_sdp(True)` / `enable_mem_efficient_sdp(True)` / `enable_math_sdp(False)`, set once before constructing the pipeline. (Switching `weight_dtype` between bf16/fp16 alone does **not** fix this — both use the same 2 bytes/element.)
3. The HF Space snapshot used to recover CatVTON's source doesn't include the safety checker's `resource/img/NSFW.jpg` placeholder asset, so leaving the safety checker enabled crashes with `FileNotFoundError` the moment it fires (even a false positive). Fix: `skip_safety_check=True` on `CatVTONPipeline`.

## 1. Known-good environment

This exact combination was installed and produced genuine, verified inference (`docs/virtual-tryon.md` §3-4):

| Package | Version |
|---|---|
| Python | 3.9.25 |
| PyTorch | 2.4.0+cu121 |
| Torchvision | 0.19.0+cu121 |
| Diffusers | 0.30.3 |
| Accelerate | 1.6.0 |
| PEFT | 0.17.1 |
| Transformers | 4.46.3 (or 4.44.2, verified separately) |
| Detectron2 | 0.6 |
| GPU | Tesla T4, 15+ GB VRAM |

## 2. Source: the original GitHub repo is gone

`https://github.com/Zheng-Chong/CatVTON` returns a genuine 404 — confirmed independently (not a Colab/Kaggle network artifact): the account itself is active, its current repo list no longer includes `CatVTON`, and the Wayback Machine shows it was alive as recently as 2026-06-10, meaning it was taken down between then and now.

**Approved alternative source**: the official author's own Hugging Face Space, at a specific historical commit —
```
Repository: https://huggingface.co/spaces/zhengchong/CatVTON
Revision:   58d5e58e9ac8e84ed71259407c4496ee9af253ea  (2024-08-08)
```
This is a verified, author-authored snapshot (same `zhengchong` namespace as the model weights), containing `model/pipeline.py` (CatVTONPipeline — exact constructor match to what VISTIQ's worker expects), `model/attn_processor.py`, `model/utils.py` (all byte-identical to the current Space `main` branch — unchanged since 2024), and `model/cloth_masker.py`. **One real difference**: this revision's masking uses `AutoMaskerSeg` + a third-party SegFormer model (`mattmdjaga/segformer_b2_clothes`) instead of the original SCHP-based `AutoMasker` — the Space's own `app.py` discloses this was done "to adapt to ZeroGPU." DensePose itself (the real detectron2-based pose estimation) is unaffected; only the human-parsing/ATR step differs. This has been accepted as the working substitute.

Download with:
```python
from huggingface_hub import snapshot_download
repo_path = snapshot_download(
    repo_id="zhengchong/CatVTON",
    repo_type="space",
    revision="58d5e58e9ac8e84ed71259407c4496ee9af253ea",
)
```

## 3. Model weights

```python
from huggingface_hub import snapshot_download
weights_path = snapshot_download(repo_id="zhengchong/CatVTON")          # attention weights (CC BY-NC-SA 4.0)
base_path = "runwayml/stable-diffusion-inpainting"                     # base inpainting model; HF resolves this
                                                                         # via a 307 redirect even though the org's
                                                                         # own page was taken down — confirmed live.
                                                                         # stable-diffusion-v1-5/stable-diffusion-inpainting
                                                                         # is the direct successor if the redirect
                                                                         # ever stops working.
```
Plus `mattmdjaga/segformer_b2_clothes` (downloaded automatically by `AutoMaskerSeg` on first use).

## 4. Detectron2 / DensePose — known pitfalls and fixes

These were diagnosed against Kaggle's base image; Colab's own image may or may not hit the same issues, but the fixes are safe and known-good if you do:

- **If `import torch.utils.cpp_extension` fails with `ModuleNotFoundError: setuptools`**: the venv has no `pip`/`setuptools`/`wheel` (happens with `uv`-created venvs). Fix: `uv pip install setuptools==69.5.1 wheel`.
- **If there is no matching CUDA toolkit for your PyTorch build** (e.g. system has CUDA 13.x but PyTorch wants cu121, and no real `nvcc` is available — a bundled `ptxas` is not a substitute): build detectron2 as a **C++-only extension** by hiding the GPU during the build only (`CUDA_VISIBLE_DEVICES=""`, `FORCE_CUDA="0"` as env vars for the `pip install` step). This selects `CppExtension` over `CUDAExtension` in detectron2's own `setup.py`. DensePose's `R_50_FPN` config does not need detectron2's custom CUDA kernels — ROIAlign/NMS delegate to torchvision, which is already CUDA-enabled — so the model still runs on GPU at inference time; only detectron2's own handful of custom CUDA ops (not used by this config) would be unavailable.
- **`AttributeError: module 'PIL.Image' has no attribute 'LINEAR'`**: detectron2 0.6 predates Pillow 10's removal of this alias. Fix: in `detectron2/data/transforms/transform.py`, replace `Image.LINEAR` with `Image.BILINEAR` (same constant, value `2`) — a one-line, mechanical patch, not a behavior change.
- **`ModuleNotFoundError: av` / `scipy`**: DensePose's own `evaluation`/`data/video` submodules import these at package-import time even though VISTIQ's usage never touches video. Fix: `pip install av scipy`.
- **If the dependency resolver pulls OpenCV 5.x**: this is a major-version jump past what CatVTON's own `requirements.txt` was written against (`opencv_python==4.10.0.84`). Pin explicitly: `pip install opencv-python-headless==4.10.0.84`.

Verify every import before proceeding to inference — do not assume success:
```python
import detectron2; detectron2.__version__      # '0.6'
import detectron2._C                           # must import without error
import densepose
from densepose.vis.densepose_results import DensePoseResultsFineSegmentationVisualizer
```

## 5. Constructing the pipeline

Exactly matching the recovered `app.py`'s own construction (do not guess at different arguments):

```python
from model.pipeline import CatVTONPipeline
from model.cloth_masker import AutoMaskerSeg

pipeline = CatVTONPipeline(
    base_ckpt="runwayml/stable-diffusion-inpainting",
    attn_ckpt=weights_path,
    attn_ckpt_version="mix",
    weight_dtype=torch.float16,
    use_tf32=True,
    device="cuda",
)
masker = AutoMaskerSeg(
    densepose_ckpt=os.path.join(weights_path, "DensePose"),
    segformer_ckpt="mattmdjaga/segformer_b2_clothes",
    device="cuda",
)
```

## 6. Genuine inference

Run on a real person/garment pair (e.g. from `resource/demo/example/` in the recovered source, or VISTIQ's own `demo-assets/`), at 768×1024, and actually inspect the output (shape, dtype, pixel-value spread) before trusting it — never report success from the pipeline merely constructing without error. A full worked example (resize, mask, call, save, verify) is in this project's development history; reconstruct it from §5 above plus `AutoMaskerSeg.__call__(image, mask_type)` (`mask_type` ∈ `upper`/`lower`/`overall`/`inner`/`outer`).

## 7. Wiring it into VISTIQ

1. Start the worker's own FastAPI app (`GET /health`, `POST /tryon` with bearer auth — see `docs/virtual-tryon.md` §9 for the exact contract) inside the GPU environment.
2. Expose it: `cloudflared tunnel --url http://127.0.0.1:<port> --no-autoupdate` for a temporary HTTPS URL (no Cloudflare account needed) — or any other secure tunnel you control.
3. In `vistiq-backend/.env`, set `VISTIQ_TRYON_WORKER_URL` to that URL and `VISTIQ_TRYON_WORKER_TOKEN` to the same bearer token the worker enforces (generate it once; never commit it). Both lines currently exist in `.env`, commented out with the previous session's now-dead values — uncomment and replace both.
4. Restart the VISTIQ backend so it re-reads `.env`, then confirm with a real try-on request through the UI — not just a health check — before considering the feature "live" again.

## 8. Safety notes carried over from this project's history

- Never click anything labeled "Factory reset," "Delete," or similar on whatever platform hosts the GPU runtime, without confirming first what it actually does — one such click previously wiped an entire working Kaggle session.
- Never restart or disconnect a runtime that has unsaved work without explicit approval.
- Preserve the original notebook/session; create a separate copy for destructive experiments if the installation needs more than one attempt.
