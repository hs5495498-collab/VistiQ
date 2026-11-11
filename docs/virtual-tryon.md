# Virtual Try-On (Phase 5 — experimental)

## 1. What this is, and what it is not

VISTIQ's Virtual Try-On feature lets a user see one of their own wardrobe garments rendered onto a photo of themselves, using [CatVTON](https://github.com/Zheng-Chong/CatVTON) — a real diffusion-based virtual try-on research model, not a crude image composite.

**What's actually implemented and verified:**
- Genuine CatVTON inference was run and produced real, visually correct results (garment color/pattern correctly transferred, pose/background preserved) — see §4.
- The full VISTIQ job lifecycle: authenticated job creation, ownership-scoped status/result retrieval, deletion, and error handling — all automated-test-covered (`vistiq-backend/tests/test_tryon_api.py`, `test_tryon_worker.py`).
- The React UI (`vistiq-frontend/src/pages/TryOn.tsx`): garment selection, photo upload, status polling, before/after comparison, history, honest unavailable/error states.
- **Phase 5.2**: the backend was connected to a genuinely running GPU worker (in Google Colab, exposed over a temporary authenticated HTTPS tunnel) and driven end-to-end through the real browser UI — see §9.
- **Phase 5.3**: an 8-sample real-world quality evaluation — real human photographs, real garment photographs, run through the actual browser UI end to end, visually scored across garment preservation / pose / background / realism / artifacts — see §10. Result: 8/8 technical success; 6/8 visually convincing garment transfer; 2/8 revealed real, disclosed limitations (one minor rendering artifact, one input-framing issue), not fabricated or hidden.

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
- Quality evaluation is now 10 sample pairs total across this project's history (§4's original 2 + §10's 8), all qualitative human ratings (1–5), not a systematic/statistical evaluation and not benchmarked against any quantitative metric (no SSIM/FID/LPIPS). The Phase 5.2 end-to-end browser verification (§9) used synthetic placeholder images (solid-color rectangles) purely to exercise the plumbing (auth, job lifecycle, storage, UI polling) — that run is not quality evidence; §4 and §10 are.
- No `lower`-category (bottoms) sample has been evaluated — CatVTON's own official demo set (§10) does not include a dedicated lower-garment example, so this remains untested with real photos, not merely under-sampled.
- One real, disclosed limitation from §10: a garment reference photo cropped to only part of a dress is sometimes misclassified by VISTIQ's own category predictor and, even once corrected, CatVTON will only recreate the visible cropped portion — the model is not shown the rest of the garment to reconstruct. This is a photo-framing issue, not a CatVTON defect; see §10's failure analysis and the "For dresses" guidance now shown in `AddItem.tsx`.
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

## 10. Real-world visual quality evaluation (Phase 5.3)

§4 established that CatVTON inference *runs*. This section asks a different question — does the generated image actually look like a convincing garment transfer? — using real photographs, run through the real VISTIQ application (not a raw inference script), scored by human visual inspection against named criteria. It does not invent or report SSIM/FID/LPIPS or any other automated metric; none were computed.

### 10.1 Dataset

8 test pairs, all sourced from CatVTON's own official demo assets — [`Zheng-Chong/CatVTON`](https://github.com/Zheng-Chong/CatVTON), commit `7818397f25613beedb3d861a34769f607cfcf3b1`, `resource/demo/example/` — licensed **CC BY-NC-SA 4.0** by the repository's own `LICENSE` and README ("All the materials, including code, checkpoints, and demo, are made available under the Creative Commons BY-NC-SA 4.0 license"), used here non-commercially for exactly the research/academic purpose that license permits. CatVTON's own `app.py` additionally credits the person photos as coming from the public demos of [OOTDiffusion](https://huggingface.co/spaces/levihsu/OOTDiffusion) and [OutfitAnyone](https://www.outfitanyone.org), and the garment photos as sourced "from the Internet" by CatVTON's authors — no personal or private photograph of any real individual outside that published demo set was used, and nothing was uploaded to any third party beyond the already-authorized VISTIQ backend and its own GPU worker.

No `lower` (bottoms) example exists in CatVTON's own official demo set — only `condition/upper` and `condition/overall` folders are provided — so this evaluation covers 4 upper-body pairs and 4 overall (dress) pairs; 6–10 pairs were requested and 8 were achievable from genuinely-licensed source material. No lower-body real-photo pair has been evaluated (see §8).

| ID | Garment (CatVTON source file) | Category → cloth_type | Person photo (CatVTON source file) |
|---|---|---|---|
| TP01 | `condition/upper/21514384_52353349_1000.jpg` — grey cardigan, Snoopy patch | Tops → upper | `person/men/Simon_1.png` |
| TP02 | `condition/upper/22790049_53294275_1000.jpg` — cream Snoopy tennis vest | Tops → upper | `person/men/Yifeng_0.png` |
| TP03 | `condition/upper/23255574_53383833_1000.jpg` — brown/white jersey, "95" | Tops → upper | `person/men/model_5.png` |
| TP04 | `condition/upper/24083449_54173465_2048.jpg` — black graphic tee | Tops → upper | `person/men/model_7.png` |
| TP05 | `condition/overall/21744571_51588794_1000.jpg` — floral dress | Dresses → overall | `person/women/049713_0.jpg` |
| TP06 | `condition/overall/22153949_52376342_1000.jpg` — lime draped dress | Dresses → overall | `person/women/1-model_3.png` |
| TP07 | `condition/overall/23962182_54027982_1000.jpg` — cream knit shirt-dress | Dresses → overall | `person/women/2-model_4.png` |
| TP08 | `condition/overall/24047235_54199143_1000.jpg` — white chevron polo dress | Dresses → overall | `person/women/model_8.png` |

No input image was cropped, retouched, or otherwise modified before upload — each was used exactly as downloaded from the source commit above.

### 10.2 How this was run

Through the actual application, not a direct-inference script: a dedicated test account was registered in the real VISTIQ frontend (`http://127.0.0.1:5173`), each garment was added via the real **Add Item** flow (real upload → real `app/services/image_validation.py` validation → real classical-CV clothing analysis for category/color suggestion → manual review of that suggestion, same as any real user would do), and each pair was then run through the real **Try-On** page: select garment → upload person photo → submit → observe the UI poll from `pending`/`processing` to a terminal state → view the rendered before/after result in the browser. All 8 jobs were created, processed, and completed through `POST /tryon`, the real background task, and the real live Colab worker over the authenticated tunnel from §9 — never a mocked `tryon_worker`.

One real, incidental finding from this process: VISTIQ's own classical clothing-image-analysis step (not CatVTON) mispredicted the category for TP06/TP07/TP08 as `Bottoms`/`Tops`/`Tops` respectively, each flagged by the UI's own low-confidence/overexposure warning — because the source photos themselves are cropped product shots showing only part of the dress. Each was manually corrected to `Dresses` before saving, exactly as the UI prompts a real user to do ("AI predicted — please review"). This is discussed further in §10.5.

### 10.3 Visual quality evaluation

Scores are **subjective human ratings, 1 (poor) to 5 (excellent)** — not an automated metric.

| ID | Garment preservation | Pose consistency | Background preservation | Realism | Artifacts | Notes |
|---|---|---|---|---|---|---|
| TP01 | 5 | 5 | 5 | 4 | None | Cardigan rendered open, bare torso visible underneath — plausible given the source photo shows no undershirt, but not what a user would expect by default. |
| TP02 | 5 | 5 | 5 | 3 | Garment-body boundary artifact | A visible texture/seam discontinuity on the legs just below the vest hem (the shorts fabric picked up an inconsistent grey patch). |
| TP03 | 5 | 5 | 5 | 5 | None | Jersey number/text fully legible, clean result. |
| TP04 | 5 | 5 | 5 | 5 | None | Graphic tee text/logo fully legible, clean result. |
| TP05 | 5 | 5 | 5 | 5 | None | Floral pattern and both colors richly preserved; clean waist-to-hem transition. |
| TP06 | 4 | 5 | 5 | 4 | None (see note) | Texture/drape/color of the *visible* garment area faithfully reproduced, but the source photo only shows the draped bodice — CatVTON correctly rendered only that, leaving jeans visible below; not a full dress. Input-framing limitation, not a model defect — see §10.5. |
| TP07 | 5 | 5 | 5 | 5 | None | Trim, buttons, and knit texture all preserved; converted a crop-top-and-skirt photo into a coherent belted shirt-dress. |
| TP08 | 5 | 5 | 5 | 5 | None | Chevron stripe colors and polo collar detail precisely preserved. |

**Garment preservation**: 6/8 scored 5/5 — color, pattern, graphics/text, and trim details were all transferred faithfully, including fine details like jersey numbers and graphic-tee text remaining legible. The 2 scores below 5 (TP02, TP06) reflect a rendering artifact and an input-framing limitation respectively, not a failure to preserve what was actually asked of the model.

**Pose and background**: 8/8 scored 5/5 on both — every result preserved the original pose, face, proportions, and background exactly, with no distortion observed in any sample.

**Artifacts**: 7/8 showed no artifacts at all (no extra limbs, no distorted hands, no missing body parts, no unnatural shadows). TP02 showed one localized garment-body boundary/texture-blend artifact on the legs. No sample showed a limb, hand, or anatomical distortion.

### 10.4 Performance

All timings below are the backend's own `TryOnJob.created_at`/`completed_at` database timestamps (real server-recorded values, not a stopwatch estimate), covering the full round trip: VISTIQ backend → authenticated HTTPS tunnel → Colab worker → CatVTON inference → PNG returned → saved by `tryon_storage`.

| ID | Garment category | Input person photo dimensions | Output dimensions | Total duration | Result |
|---|---|---|---|---|---|
| TP01 | upper | 960×1280 | 768×1024 PNG | 77.73 s | success |
| TP02 | upper | 960×1280 | 768×1024 PNG | 79.61 s | success |
| TP03 | upper | 768×1024 | 768×1024 PNG | 77.79 s | success |
| TP04 | upper | 768×1024 | 768×1024 PNG | 79.30 s | success |
| TP05 | overall | 768×1024 | 768×1024 PNG | 78.73 s | success |
| TP06 | overall | 768×1024 | 768×1024 PNG | 80.26 s | success |
| TP07 | overall | 768×1024 | 768×1024 PNG | 80.19 s | success |
| TP08 | overall | 768×1024 | 768×1024 PNG | 76.96 s | success |

- Successful jobs: **8 / 8**. Failed jobs: **0**.
- Success rate: **100%** (8/8).
- Average total duration: **78.82 s**. Median: **79.02 s**. Range: 76.96 s–80.26 s (a 3.3 s spread — consistent, not bimodal between garment categories).
- CatVTON always produced a 768×1024 output regardless of the input person photo's own resolution (960×1280 inputs were resized internally) — consistent with the §3/§4 working resolution.
- GPU memory was **not independently re-instrumented per job for this batch** (no live `nvidia-smi` monitoring was attached to these specific 8 runs) — this is a real, disclosed gap, not a zero. The only GPU memory figures on record for this pipeline are from separate, earlier single-request measurements (§4: ~5.25 GB allocated / ~7.27 GB reserved; §9: ~7 GB used), included here as reference points only, not as a measurement of these 8 jobs specifically.

### 10.5 Failure analysis

No job failed at the API, validation, or inference level (8/8 completed). The two sub-5 visual scores break down as:

- **TP02 (garment-body boundary artifact)** — a model inference quality issue: CatVTON produced a visible texture discontinuity on the legs just below the vest hem. The input images (vest photo, person photo) were both valid, well-lit, and correctly categorized — this was not an input-quality problem. Classified as: **visually imperfect but technically successful** result.
- **TP06 (incomplete dress representation)** — not a CatVTON or VISTIQ bug: the source garment photograph itself (CatVTON's own official demo asset) is cropped to show only the draped bodice of the dress, not its full length. VISTIQ's classical category predictor read this (reasonably) as `Bottoms`/`Tops`-like for TP06/07/08, each correctly flagged by the UI's own low-confidence warning for manual review; once corrected to `Dresses`, CatVTON faithfully rendered exactly the garment region it was shown. The model cannot reconstruct the hidden, out-of-frame portion of a garment. Classified as: **input/data limitation**, distinct from a model-inference failure — and the reason §10.2's finding led directly to the §10.6 improvement.

No occlusion, incorrect garment category (after manual correction), unsupported garment type, or GPU memory constraint was observed as a cause of any issue in this batch.

### 10.6 Improvement implemented (evidence-based)

**Change**: `vistiq-frontend/src/pages/AddItem.tsx` now shows an additional styling tip — "For dresses: frame the full garment from shoulder to hem. A photo cropped to just part of the dress (e.g. only the bodice) can be misread as a top, and Virtual Try-On will only recreate the visible portion." — whenever the selected category is `Dresses`. It does not touch classification logic, the recommendation engine, or any existing behavior for other categories; it is additive UI guidance only.

**Evidence it addresses**: 3 of the 4 dress samples in this batch (TP06, TP07, TP08) were initially mispredicted as `Bottoms`/`Tops` by the existing classical-CV category step specifically because the source photos were cropped product shots, and TP06's result was visibly incomplete as a direct consequence of that same framing (§10.5). This tip targets the actual, observed cause.

**Before/after**: verified directly in the running app — selecting any other category shows only the existing "flat-lay photo" tip; selecting `Dresses` additionally shows the new tip (confirmed via browser screenshot during this session, not committed as an image). No change to `is_worker_configured`, the category classifier itself, scoring, or recommendation logic.

**Regression check**: `npm run lint` and `npm run build` (`tsc -b && vite build`) both clean after the change — see §11 (Testing, root README).

### 10.7 What this evaluation does and does not establish

Does establish: CatVTON, driven through VISTIQ's real UI with real human and garment photographs, reliably completes (8/8) and in the large majority of cases (6/8) produces a visually convincing, artifact-free garment transfer with preserved pose and background, within a consistent ~77–80 s window per request on a single T4. Does not establish: performance under concurrent load, performance on `lower`-category garments (no real sample available — see §8), a statistically significant quality rate (n=8, qualitative only), or any claim that the one observed rendering artifact (TP02) never recurs.
