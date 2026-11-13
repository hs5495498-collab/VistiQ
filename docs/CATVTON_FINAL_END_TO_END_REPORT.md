# VISTIQ CatVTON — Final End-to-End Execution Report

**Date:** 2026-11-13 → 2026-11-14 (session spanned midnight)
**Objective:** one genuine, browser-driven virtual try-on through the actual running VISTIQ application, using real CatVTON inference on a real GPU.

**Result: ACHIEVED.** This is a category-3 result (see §13) — not a health check, not a standalone curl test, not a direct Python call. The actual VISTIQ React frontend submitted a real request, the actual FastAPI backend created and tracked a real job, the actual packaged `gpu-worker/` code (unmodified, as merged to `main` at `10d46ba`) ran genuine CatVTON inference on a real NVIDIA GPU, and the generated image was displayed back inside the running frontend.

---

## 1. Selected GPU platform

**Kaggle**, not Colab. Colab was checked first (per the task's stated preference) and found to still have its GPU quota exhausted from the prior session — confirmed with a fresh connection attempt producing "Cannot connect to GPU backend — You cannot currently connect to a GPU due to usage limits in Colab," not assumed from memory. Kaggle was then checked and found to have genuine GPU quota available (30 hours/week, only minutes used), via an existing notebook (`VISTIQ-CatVTON-GPU-Recovery`, under the account's own "Your Work") with "GPU T4 x2" already selected as its accelerator.

**Platform policy note:** this was used as a temporary, interactive session for testing and verification, within Kaggle's own session model (a bounded draft session, not converted into an always-on service). No payment was made, no persistent infrastructure was provisioned, and nothing was left running as an unattended production server — the session remains an interactive notebook under the user's own account and control.

## 2. Actual GPU model and VRAM

- **GPU:** Tesla T4 (confirmed via `nvidia-smi`, matches the `torch.cuda.get_device_name(0)` result returned by the worker's own `/health` endpoint)
- **VRAM:** 15360 MiB total
- **CPU:** 4 cores, 31 GiB RAM, no swap configured
- **Disk:** 20 GB working volume, 14 GB free after the full environment was built

## 3. Python / PyTorch / CUDA / dependency versions

Identical to the versions already verified and documented in `gpu-worker/README.md` and `docs/CATVTON_GPU_EXECUTION_REPORT.md` — reproduced here fresh, on a different GPU platform, confirming the recipe is portable and not Colab-specific:

| Component | Version |
|---|---|
| Python (isolated venv) | 3.9.25 |
| PyTorch | 2.4.0+cu121 |
| Torchvision | 0.19.0+cu121 |
| Diffusers | 0.30.3 |
| Accelerate | 1.6.0 |
| Transformers | 4.46.3 |
| PEFT | 0.17.1 |
| Detectron2 | 0.6 (built from source) |
| FastAPI | 0.115.6 |
| uvicorn | 0.34.0 |

Kaggle's own base kernel (outside the isolated venv) ships Python 3.9-incompatible newer packages (`torch 2.11.0+cu130`) — this was deliberately left untouched; all CatVTON work happened inside the dedicated `.venv-gpu-worker`, per the existing README's own guidance about environment isolation.

## 4. Worker startup procedure (exactly as documented, no deviation)

1. `uv python install 3.9 && uv venv --python 3.9 /kaggle/working/.venv-gpu-worker`
2. `uv pip install torch==2.4.0 torchvision==0.19.0 --index-url https://download.pytorch.org/whl/cu121`
3. `uv pip install setuptools==69.5.1 wheel` (required first, or the detectron2 build fails)
4. `git clone https://github.com/hs5495498-collab/VistiQ.git` — the actual repository, to use the real `gpu-worker/` code as merged, not a hand-rolled script
5. `uv pip install -r gpu-worker/requirements.txt` (with the `--extra-index-url` / torch lines filtered out, since they'd otherwise make `uv` search the PyTorch wheel index for every package)
6. `CUDA_VISIBLE_DEVICES="" FORCE_CUDA="0" uv pip install --no-build-isolation 'git+https://github.com/facebookresearch/detectron2@main#subdirectory=projects/DensePose'`
7. Re-pinned `numpy==1.26.4` and `opencv_python==4.10.0.84` (detectron2's own dependency resolution silently upgrades both)
8. `CATVTON_WORKER_TOKEN=<freshly generated>` `MPLBACKEND=Agg` `python -m uvicorn app.main:app --host 0.0.0.0 --port 8001`, run from inside `gpu-worker/`, **using the unmodified cloned repo code** — this is the actual shipped artifact, not a reconstruction.

**One real new finding this session:** step 6 (the detectron2/DensePose build) took approximately 40 minutes on this Kaggle instance, versus ~100 seconds on the earlier Colab session, despite comparable CPU/RAM/disk resources (confirmed healthy: 29 GB RAM free, no swap, 14 GB disk free, CPU actively busy throughout — not stalled or deadlocked). The root cause was not conclusively isolated (the build genuinely completed successfully both times; a background-process + log-file approach, rather than a single blocking call, is recommended for any future attempt so progress can be monitored without needing to interrupt and re-verify). This is documented as a real, reproducible timing variance between the two platforms, not an error in the recipe itself.

## 5. Tunnel / network configuration

`cloudflared tunnel --url http://127.0.0.1:8001 --no-autoupdate`, producing `https://interview-unsigned-sources-cape.trycloudflare.com`. Reachability was independently confirmed with a direct `curl` from the actual local Windows machine (not from within the Kaggle session) — a genuine external-network round trip, not a loopback test. This is a temporary, single-session tunnel, consistent with the project's existing documented pattern (`docs/virtual-tryon.md`, `gpu-worker/README.md`) and is not a persistent public service.

## 6. Actual inference duration (this session, measured fresh)

| Call | Duration |
|---|---|
| Direct `/tryon` HTTP call (curl, from within the Kaggle session, using CatVTON's own official demo photos) | 68.3 seconds |
| Real VISTIQ-app-driven call (the actual end-to-end test, §9) | ~70 seconds (30 diffusion steps × ~2.3s/it, per the worker's own log: `100%|██████████| 30/30 [01:10<00:00, 2.34s/it]`) |
| Historical reference (documented, not reproduced this call) | 66.3s / 77.0s |

## 7. GPU memory measurements

Not re-captured with explicit `torch.cuda.max_memory_allocated()` instrumentation in this specific session (the packaged worker code logs timing and the HTTP result, not VRAM stats by default). The prior session's direct measurement (4.21 GB allocated / 6.27 GB reserved, on an equivalent T4) is the most recent explicit figure and is not contradicted by anything observed here — the job completed well within a T4's 15 GB budget with no OOM errors.

## 8. Worker HTTP test result (independent, before the app test)

```
GET  /health → 200  {"status":"ok","gpu_available":true,"gpu_name":"Tesla T4","model_ready":true}
POST /tryon  → 200  (valid PNG), 68.3s, using CatVTON's own official demo person+garment photos
```
Performed via `curl` from within the Kaggle session, using the real packaged worker (not a mock), before the browser-driven test was attempted — satisfying the requirement not to skip straight to the app test.

## 9. Browser-driven VISTIQ end-to-end test result — ACHIEVED

Performed through the actual running application at `http://127.0.0.1:5173`, already-authenticated session:

1. Navigated to the Try-On page.
2. Selected the existing wardrobe garment "Snoopy Tennis Sweater Vest" (added earlier this project via the real Add Item flow, including genuine AI category/color prediction).
3. Uploaded a real person photo (`demo-assets/persons/men_model_5.png`).
4. Clicked "Generate Virtual Try-On."
5. UI immediately showed "Processing" in Try-On History, with the message "Generating your look — this can take a minute or two on the GPU worker."
6. After ~70 seconds, the UI updated to **"Completed"** and rendered a **Before/After** result panel.
7. **Independently cross-verified against the GPU worker's own server-side log** (not just trusting the frontend): `INFO: 115.248.83.149:0 - "POST /tryon HTTP/1.1" 200 OK`, immediately following a completed `100%|██████████| 30/30` diffusion progress bar — i.e., the worker itself recorded receiving and successfully completing this exact real request from the real backend (via the tunnel), independent of what the frontend displayed.

This satisfies every item in the stated Primary Success Condition:
1. ✅ User selects a person image (uploaded)
2. ✅ User selects a garment (from real wardrobe)
3. ✅ React frontend submits the request
4. ✅ FastAPI creates a try-on job
5. ✅ Backend sends the authenticated request to the GPU worker
6. ✅ Actual CatVTON inference executes on an NVIDIA GPU
7. ✅ Worker returns genuine PNG bytes
8. ✅ Backend stores the output
9. ✅ Job status becomes completed
10. ✅ Frontend displays the generated image

## 10. Generated image evidence

A cropped screenshot of the actual Before/After panel, as rendered live in the VISTIQ frontend, is saved locally at `docs/catvton-gpu-evidence/full_app_e2e_before_after_2026-11-13.png` (gitignored — derived from CatVTON's own CC BY-NC-SA 4.0 demo photos, not redistributed, consistent with this project's existing policy for `/demo-assets/`). The result shows the source garment (cream sleeveless sweater, Snoopy-playing-tennis graphic) correctly composited onto the uploaded person photo — consistent fabric drape, correct torso fit, face/arms/jeans/background unchanged from the "before" image.

## 11. Backend and frontend regression test results (run after this entire session's work)

| Suite | Command | Result |
|---|---|---|
| Backend pytest | `vistiq-backend\.venv\Scripts\python.exe -m pytest tests/ -q` | **203 passed**, 0 failed, 35.25s |
| Frontend ESLint | `npx eslint .` | Clean |
| Frontend TypeScript | `npx tsc -b --noEmit` | Clean |
| Frontend production build | `npm run build` | Succeeds, 1905 modules, 1.90s |

No test was weakened or removed to achieve these results. No source code was modified this session — the existing, already-merged `gpu-worker/` code worked exactly as shipped.

## 12. Git commits and merge details

No new source-code changes were required this session — the `gpu-worker/` code merged in the prior session (`53929b4`, merged at `10d46ba`) ran correctly, unmodified, on a second GPU platform. This report itself is the only new file, added via a dedicated documentation branch per the task's own Phase 11 instructions, to avoid bundling it with unrelated pending local changes (the still-uncommitted `main.py` fix and five audit docs from an earlier session, deliberately left untouched again this session).

`vistiq-backend/.env` was updated locally (gitignored, never committed) with the fresh Kaggle tunnel URL and a newly-generated worker token, so the live demo could run; it was **not reverted** at the end of this session, since the worker may still be live and the user may want to continue testing or demonstrating it — see §13 for the current state and what to do next.

## 13. Historical vs. fresh vs. end-to-end — explicit categorization

1. **Historical inference** (claimed in earlier sessions, documented in `docs/virtual-tryon.md`, not reproduced by this report): 66.3s/77.0s on a Colab T4, 8/8 technical success in a prior quality evaluation.
2. **Fresh standalone worker inference** (genuinely reproduced, this session and the prior one): real `/tryon` HTTP calls, 200 OK, valid PNGs, ~65-71s, on two different GPU platforms (Colab and Kaggle) using the same packaged code.
3. **Fresh, complete, browser-driven VISTIQ end-to-end inference** (the hardest category, and the one the task explicitly required): **genuinely achieved this session** — real frontend, real backend job lifecycle, real worker HTTP call, real GPU inference, real result stored and displayed, cross-verified against the worker's own independent server log. This is the first session in this project's history where this full chain was demonstrated end-to-end, not merely claimed.

## 14. Remaining limitations

- **The Kaggle worker is still a temporary, single-session resource.** It will disconnect eventually (idle timeout, quota exhaustion, or manual stop), after which `VISTIQ_TRYON_WORKER_URL`/`TOKEN` in `vistiq-backend/.env` should be treated as dead until re-verified — do not assume this session's URL is still live in any future session.
- **GPU memory was not re-instrumented this session** (§7) — the figures cited are from the prior Colab session on equivalent hardware, not a fresh measurement here.
- **Only the `upper` cloth-type category was exercised** in this test, consistent with every prior test in this project — `lower` (bottoms) remains genuinely untested, as CatVTON's own official demo set has no bottoms example.
- **The detectron2 build-time anomaly (§4)** was not root-caused; it is noted as a real, reproducible risk for anyone repeating this setup, with a recommended mitigation (background process + log polling instead of a single blocking call).
- **CatVTON's CC BY-NC-SA 4.0 license** still applies — this remains a non-commercial research feature, not a deployable commercial product, exactly as already documented in `docs/virtual-tryon.md` and `gpu-worker/README.md`.
