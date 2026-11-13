# VISTIQ CatVTON GPU worker

A standalone FastAPI service that runs genuine CatVTON virtual try-on
inference on an NVIDIA GPU. It is intentionally independent of
`vistiq-backend` (which is CPU-only) -- run this in its own environment,
on a machine or notebook (Google Colab, Kaggle, a GPU VM, etc.) that
actually has an NVIDIA GPU.

**Status, as of 2026-11-13**: this exact code was built from a session
that achieved genuine, verified, real-GPU inference through this worker's
own HTTP contract (curl-tested, `200 OK`, valid 768x1024 PNG, 71.5s,
matching historical timings). The Colab free-tier GPU quota then ran out
before a full VISTIQ-app end-to-end UI test could be completed in that
same session. See `docs/CATVTON_GPU_EXECUTION_REPORT.md` at the repo root
for the full, evidence-based writeup of what was and wasn't verified.

## 1. Source and license

- **CatVTON's own GitHub repository** (`github.com/Zheng-Chong/CatVTON`)
  returns a genuine HTTP 404 as of 2026-11-13 (confirmed directly) -- it
  has been taken down. This worker instead builds the pipeline from the
  author's own HuggingFace Space snapshot, same `zhengchong` namespace as
  the published model weights, pinned to a specific historical revision
  for reproducibility: `zhengchong/CatVTON` (Space), revision
  `58d5e58e9ac8e84ed71259407c4496ee9af253ea`.
- **Model weights**: `zhengchong/CatVTON` (CC BY-NC-SA 4.0 -- non-commercial,
  share-alike, attribution required) plus the base
  `runwayml/stable-diffusion-inpainting` model and
  `mattmdjaga/segformer_b2_clothes`. **Do not deploy this worker as part
  of a commercial product** without a different license or an explicit
  commercial grant from the CatVTON authors.
- Everything is downloaded automatically via `huggingface_hub` the first
  time the worker starts -- there is nothing to manually place in this
  directory.

## 2. Environment setup (verified exact recipe)

Tested on Python 3.9.25, a Tesla T4 (driver 580.82.07, reported CUDA
13.0). Use a **dedicated virtual environment**, separate from
`vistiq-backend/.venv`.

```bash
# 1. Create and activate a Python 3.9 venv
#    (on Colab/Kaggle, `uv` is usually already available and fastest):
uv python install 3.9
uv venv --python 3.9 .venv-gpu-worker
# then use .venv-gpu-worker/bin/python for every command below

# 2. Install torch from the CUDA 12.1 index FIRST
uv pip install --python .venv-gpu-worker/bin/python \
    torch==2.4.0 torchvision==0.19.0 \
    --index-url https://download.pytorch.org/whl/cu121

# 3. setuptools/wheel BEFORE anything that builds from source -- a fresh
#    uv-created venv has neither, and detectron2's build fails with
#    "error: invalid command 'bdist_wheel'" without them.
uv pip install --python .venv-gpu-worker/bin/python setuptools==69.5.1 wheel

# 4. The rest of requirements.txt
uv pip install --python .venv-gpu-worker/bin/python -r requirements.txt
```

### Detectron2 + DensePose (not a plain pip requirement)

CatVTON's mask generation depends on DensePose, which depends on
detectron2. Build it from the **official, still-maintained**
`facebookresearch/detectron2` repository -- not from Zheng-Chong's fork,
which no longer exists:

```bash
CUDA_VISIBLE_DEVICES="" FORCE_CUDA="0" \
uv pip install --python .venv-gpu-worker/bin/python --no-build-isolation \
    'git+https://github.com/facebookresearch/detectron2@main#subdirectory=projects/DensePose'
```

Why the env vars: on a GPU whose driver reports a newer CUDA version than
the installed PyTorch build was compiled for (e.g. driver reporting CUDA
13.0 while PyTorch is a cu121 build), detectron2's CUDA-kernel build
fails with a CUDA/PyTorch version-mismatch error. Building it as a
C++-only extension (by hiding the GPU from the build step only) avoids
this. **This does not reduce functionality here**: DensePose's
`R_50_FPN` config doesn't use detectron2's own custom CUDA kernels --
ROIAlign/NMS already delegate to torchvision, which is CUDA-enabled
independently -- so inference still runs on GPU.

The detectron2 install step also tends to silently upgrade `numpy` and
pull in `opencv-python-headless` alongside the already-installed
`opencv_python` (two different PyPI packages providing the same `cv2`
import name -- whichever installs last wins the actual files on disk).
If you hit odd `cv2`/`numpy` version mismatches afterwards, re-pin:

```bash
uv pip install --python .venv-gpu-worker/bin/python numpy==1.26.4
uv pip uninstall --python .venv-gpu-worker/bin/python opencv-python-headless
uv pip install --python .venv-gpu-worker/bin/python --force-reinstall --no-deps opencv_python==4.10.0.84
```

Verify before proceeding:
```bash
.venv-gpu-worker/bin/python -c "import detectron2; print(detectron2.__version__); import densepose; print('densepose OK')"
```
Expect `0.6` and `densepose OK`.

## 3. Configuration

```bash
cp .env.example .env
# edit .env: set CATVTON_WORKER_TOKEN to a freshly generated random value
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 4. Starting the worker

```bash
cd gpu-worker
export $(grep -v '^#' .env | xargs)   # or just export CATVTON_WORKER_TOKEN=... directly
export MPLBACKEND=Agg                  # see Troubleshooting below
.venv-gpu-worker/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

First startup takes a while (loads/downloads several GB of model weights
and constructs the pipeline) -- wait for the log line `CatVTON pipeline
ready.` before sending requests. Verified first-call timing: pipeline
construction ~20-30s, automasker construction ~3s.

## 5. Exposing it (for a local VISTIQ backend running elsewhere)

```bash
# Download cloudflared (Linux example; see cloudflare's own docs for other OSes)
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cloudflared
chmod +x cloudflared
./cloudflared tunnel --url http://127.0.0.1:8001 --no-autoupdate
```
This prints a `https://<random-words>.trycloudflare.com` URL. It is
**single-session** -- it dies when this process (or the whole
Colab/Kaggle runtime) disconnects. Always re-verify with
`GET {url}/health` before relying on it in a new session; never assume a
previously-recorded URL is still live.

Then, in `vistiq-backend/.env`:
```
VISTIQ_TRYON_WORKER_URL=https://<the tunnel's current URL>
VISTIQ_TRYON_WORKER_TOKEN=<the same value as this worker's CATVTON_WORKER_TOKEN>
```

## 6. Verifying it works (do this before trusting it from the app)

```bash
# 1. Health check
curl -s http://127.0.0.1:8001/health
# {"status":"ok","gpu_available":true,"gpu_name":"Tesla T4","model_ready":true}

# 2. A real authenticated inference call (use any real person+garment photos)
curl -s -o result.png -w '%{http_code}\n' -X POST http://127.0.0.1:8001/tryon \
    -H "Authorization: Bearer $CATVTON_WORKER_TOKEN" \
    -F "person_image=@/path/to/person.jpg" \
    -F "garment_image=@/path/to/garment.jpg" \
    -F "cloth_type=upper"
# Expect: 200, and result.png is a valid, non-trivial PNG.
```
Do not consider the worker "working" from a health check alone -- the
`/health` endpoint never touches the model. Only a real `/tryon` call
proves genuine inference.

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `error: invalid command 'bdist_wheel'` during detectron2 install | uv-created venv has no `wheel`/`setuptools` | Step 3 above, before the detectron2 install |
| detectron2 build fails with a CUDA/PyTorch version mismatch | GPU driver reports a newer CUDA than the installed torch build | Use the `CUDA_VISIBLE_DEVICES=""`/`FORCE_CUDA="0"` C++-only build (§2) |
| `torch.OutOfMemoryError: ... Tried to allocate 18.00 GiB` on a T4-class GPU | PyTorch's SDPA silently used the "math" (full materialization) attention backend instead of flash/memory-efficient | Already handled in `app/catvton_service.py` (`enable_flash_sdp`/`enable_mem_efficient_sdp`/`disable math_sdp`) -- if you still see this, verify those three lines actually execute before the pipeline is constructed |
| `FileNotFoundError: .../resource/img/NSFW.jpg` during a `/tryon` call | The safety checker's NSFW-placeholder image isn't included in the HF Space snapshot download | Already handled (`skip_safety_check=True` in `catvton_service.py`) |
| `ValueError: Key backend: 'module://matplotlib_inline.backend_inline' is not a valid value` | The worker process inherited a Jupyter/Colab-only `MPLBACKEND` env var that doesn't exist in this venv | Set `MPLBACKEND=Agg` before starting the worker (§4) |
| `cv2`/`numpy` behaving unexpectedly after installing detectron2 | detectron2's own dependencies silently upgraded them | Re-pin as shown at the end of §2 |

## 8. What this worker does and does not do

- Runs real CatVTON inference (DDIM diffusion, 30 steps, guidance scale
  2.5) on a 768x1024 image, matching the project's documented historical
  benchmarks (~66-77s, ~5-7GB VRAM on a T4).
- Does **not** implement the original SCHP-based masking (the HF Space
  revision this is built from uses `AutoMaskerSeg`, a SegFormer-based
  human-parsing model, instead) -- DensePose pose estimation is
  unaffected and still detectron2-based.
- Does **not** persist anything -- every request is processed
  independently; there is no job queue or database here (that lives in
  `vistiq-backend`).
- Serves requests one at a time (`asyncio.Lock`) -- a single GPU cannot
  usefully run concurrent diffusion passes.
