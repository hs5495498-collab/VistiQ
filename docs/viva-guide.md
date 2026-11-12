# VISTIQ — Viva Preparation Guide

Every answer here is grounded in the actual source code in this repository (file paths given throughout), verified during development — not textbook answers bolted on afterward. Where something is a genuine limitation, it's stated as one.

---

## 1. Project architecture

**One-line:** React 19 + TypeScript frontend, FastAPI + SQLAlchemy + SQLite backend, two optional ML components (a CPU clothing classifier and a remote-GPU virtual try-on worker), fully separated over HTTP.

**Detailed:** The frontend (`vistiq-frontend/`) and backend (`vistiq-backend/`) are independent processes — the frontend only ever talks to the backend over HTTP with cookies, never shares memory or imports backend code. The backend owns all state in a single SQLite file. Two further subsystems hang off the backend: `ml/` (the classifier + classical CV pipeline, imported directly as a sibling Python package) and a separate, optionally-connected GPU worker for virtual try-on (CatVTON), reached only over an authenticated HTTPS tunnel — never imported or run in-process.

**Why this split?** The laptop running VISTIQ has no NVIDIA GPU. The classifier is small enough (~2.5M params) to run on CPU in under a second; CatVTON's diffusion model is not, so it has to live somewhere with a GPU — hence the remote worker architecture.

**Follow-up: "Why SQLite and not Postgres?"** Single-user local prototype scope — no concurrent-write contention to worry about, zero setup, and the file itself is the entire deployment artifact. A real multi-user product would need to migrate, and nothing in the SQLAlchemy layer is SQLite-specific enough to make that hard.

**Follow-up: "What's the biggest architectural risk?"** The GPU worker is not a permanent service — it's a Colab notebook, which disconnects and has a free-tier usage quota. The application handles this honestly (an "unavailable" state, never a fake result) but it is a real single point of failure for that one feature, by design of the hardware constraint, not an oversight.

---

## 2. Machine learning — the clothing classifier

**One-line:** MobileNetV3-Small, ImageNet-pretrained, fine-tuned by transfer learning on 6 VISTIQ categories, running CPU-only inference.

### MobileNetV3-Small
**One-line:** A small, efficient CNN architecture designed for mobile/edge devices.
**Detailed:** ~2.5M parameters (vs. tens of millions for ResNet-50 etc.). Uses depthwise-separable convolutions and squeeze-and-excitation blocks to get good accuracy per FLOP. Chosen here specifically because it needs to run on CPU, with no GPU available on the dev machine.

### Transfer learning
**One-line:** Reuse a model already trained on a large dataset, and retrain only part of it for your own task.
**Detailed:** `ml/training/model.py` loads MobileNetV3-Small with its ImageNet-pretrained weights, then replaces the final `Linear` classification layer (1000 ImageNet classes → 6 VISTIQ classes). Training is two-phase (`ml/training/train.py`): Phase 1 freezes everything except the new head and trains just that (8 epochs, LR 1e-3); Phase 2 unfreezes the last 3 backbone blocks and fine-tunes everything unfrozen at a much lower LR (1e-5, 6 epochs) so the pretrained low-level features (edges, textures) aren't destroyed.
**Follow-up: "Why not train from scratch?"** Not enough data (clothing-dataset-small's `train/` split is a few thousand images) to learn good low-level visual features from nothing — transfer learning lets the model start already knowing what edges/textures/shapes look like.

### `state_dict`
**One-line:** A Python dict mapping each layer's name to its learned weight tensor.
**Detailed:** `torch.save(model.state_dict(), path)` is what produces `models/vistiq_clothing_classifier.pt`. Loading it back with `strict=True` (`ml/training/model.py:load_model`) means every key and every tensor shape must match the freshly-built architecture exactly — this is how you *prove* a checkpoint matches its model definition rather than silently loading a wrong/stale one. Verified by `vistiq-backend/tests/test_model_smoke.py`.

### Softmax and confidence
**One-line:** The classifier outputs 6 raw scores (logits); softmax turns them into probabilities that sum to 1; the winning class's probability is "confidence."
**Detailed:** `ml/inference/predict.py`: `torch.softmax(logits, dim=1)`, then `argmax` for the category, `probabilities[top_index]` for confidence. A `LOW_CONFIDENCE_THRESHOLD = 0.60` flags uncertain predictions for user review — it is a UX threshold, not a claim about the model's real-world accuracy.
**Follow-up: "Does high confidence mean correct?"** No — confidence reflects the model's *own* certainty given its training, not ground truth. In our own 8-sample demonstration evaluation, a wrong prediction (lime dress → "Bottoms") came with low, self-flagged confidence (52%) — exactly the failure mode you want, but it's not guaranteed in general.

### Preprocessing
**One-line:** Resize to 224×224, convert to tensor, normalize with ImageNet's channel mean/std.
**Detailed:** Identical transform in training (`dataset.py`) and inference (`predict.py`) — `IMAGE_SIZE=224`, `IMAGENET_MEAN=[0.485,0.456,0.406]`, `IMAGENET_STD=[0.229,0.224,0.225]` (`ml/training/config.py`). Matching train/inference preprocessing exactly matters — a mismatch here is a classic, easy-to-miss bug that silently degrades accuracy.

### CPU inference
**One-line:** A single forward pass with no gradient tracking, cheap enough for real-time use on a CPU.
**Detailed:** `with torch.no_grad(): logits = model(input_tensor)` — no backward pass, no gradients computed or stored, which is most of what makes inference cheaper than training. Verified running end-to-end with no CUDA involved anywhere.

### Known limitations (say these unprompted if asked about accuracy)
- Only 6 broad categories; "Accessories" in the training data effectively only means "hat" (the only source class mapped to it) — it will not recognize bags, jewelry, belts.
- No non-clothing / out-of-distribution rejection — a solid-color image or an arbitrary photo still gets *some* category prediction, just possibly low-confidence.
- The historical **90.86% test accuracy** is the training run's own self-reported number from the Colab notebook — this repository does not contain the held-out test split to independently re-derive it, and that is disclosed, not hidden (`ml/README.md`).
- A demonstration evaluation this project (8 real photos, 4 of 6 categories — no real Outerwear/Accessories photo exists anywhere in the repo) got 7/8 correct — explicitly a small sample, not a statistically valid accuracy claim.

---

## 3. Computer vision — color and quality

### OpenCV / GrabCut
**One-line:** A classical (non-learned) iterative foreground/background segmentation algorithm.
**Detailed:** `ml/inference/segmentation.py`. Seeds a rectangle assuming the garment is roughly centered (background near the edges — true for flat-lay/product photos), then runs OpenCV's `cv2.grabCut` for 5 iterations. Images are downscaled to a max dimension of 300px first — full-resolution GrabCut was measured at up to 74s on a real upload; downscaling brought that to 0.3–1.8s. A foreground-fraction sanity check (must be 5%–95% of the image) catches degenerate results and reports failure rather than trusting a bad mask.
**Follow-up: "Is this a learned/AI segmenter?"** No — explicitly not. It's a classical energy-minimization algorithm (Rother, Kolmogorov & Blake, 2004), ships inside OpenCV, no weights, no training, fully deterministic for a fixed input.

### HSV and K-means color extraction
**One-line:** Convert the masked foreground pixels to HSV, cluster them with K-means, report the dominant cluster's color.
**Detailed:** `ml/inference/color_advanced.py`. Falls back automatically to a simpler Phase-1 deterministic method (`ml/inference/color.py`) if GrabCut fails or K-means can't produce a trustworthy result — the API's `color_confidence` field is a real cluster-dominance score when the primary path succeeds, and `null` (never a fabricated number) when it fell back.
**Follow-up: "Why HSV, not RGB?"** Hue separates color identity from lighting/shadow variation (value) better than RGB does — two photos of the same navy shirt under different lighting are closer in HSV hue than in raw RGB.

### Laplacian variance (blur detection)
**One-line:** Low variance in the image's Laplacian (second-derivative edge response) means few sharp edges — usually a blurry photo.
**Detailed:** `ml/inference/image_quality.py` — computed on a fixed 300×300 resize specifically so the threshold doesn't depend on the original photo's resolution. `BLUR_VARIANCE_THRESHOLD = 60.0`, below which a warning (not a rejection) is shown.

### Brightness / exposure
Mean grayscale pixel value, 0–255; below 35 is flagged dark, above 230 is flagged overexposed — both warnings, never hard rejections.

### Honest limitations
- GrabCut assumes a centered garment — an off-center photo or a garment worn by a person filling the frame will typically fail the sanity check and fall back to the simpler method, not produce a wrong mask silently.
- Segmentation/color is a *suggestion* surfaced to the user for confirmation — never silently trusted or auto-saved without review.
- A genuinely uniform/degenerate image (no real clothing, a solid color) was observed during evaluation to take unusually long (~90s+) to process — a real, disclosed performance finding, not something papered over.

---

## 4. Recommendation engine

**One-line:** A deterministic, rule-based hybrid scorer — six weighted compatibility dimensions, template-based candidate generation, no ML, no randomness.

### Candidate generation
`app/recommendation/engine.py`. Wardrobe pool grouped by category → matched against 6 fixed outfit templates (e.g. `top_bottom_footwear`, `dress_footwear` — "full" tier; `top_bottom`, `dress_alone`, etc. — "partial" tier, used only when no full template is satisfiable) → Cartesian product per template (capped at 200 combinations), deduplicated by exact item-id set.

### Exact scoring formula
```
score_0_100 = 100 × (
    0.30 × color_score
  + 0.20 × category_score
  + 0.20 × style_score
  + 0.15 × occasion_score
  + 0.10 × preference_score   (wear_count / 10, capped at 1.0)
  + 0.05 × weather_score
)
+ personalization_adjustment   (capped additive: ±6 color pref, -10 avoided color, +6 favorites)
```
(`app/recommendation/scoring.py` — weights sum to 1.0, verified directly from source.)

**Color** uses real hue-wheel theory (`color_theory.py`): complementary (~150–210° apart), analogous (≤40° apart), monochromatic (same hue), neutral-pairing bonuses, checked against a classic/neutral lookup table first, down-weighted toward neutral (0.5) when the item's photo-extracted color reliability is "low."

**Category** is a hand-built complementarity table (Tops pairs with Bottoms/Outerwear/Footwear/Accessories, same-category pairs score 0, etc. — `rules.py`).

### Jaccard similarity
**One-line:** `|A ∩ B| / |A ∪ B|` — the fraction of two sets' combined items that they share.
**Detailed:** Used over item-ID sets to measure how much two candidate outfits overlap.

### MMR (Maximal Marginal Relevance) diversity reranking
**One-line:** Greedily pick the next-best outfit, discounted by how much it overlaps what's already been chosen.
**Exact formula** (`app/recommendation/diversity.py`): `mmr_value = raw_score − 0.35 × max_jaccard_overlap_with_selected × raw_score`, searched within a window of `max(30, top_k × 10)` candidates. Deterministic: ties broken by original score-then-id order.
**Follow-up: "Can diversity promote a bad outfit?"** No — by construction. It only ever *reorders among* already-ranked candidates; rank #1 is always the single best-scored outfit in the search window, full stop. It trades off which of several close-scoring outfits get shown, never quality for novelty.

### Anchor-item enforcement
**One-line:** A user-selected item that every returned outfit is structurally guaranteed to include.
**Detailed:** Enforced at template-selection time (`_select_templates`): a template is only usable if the anchor's category is one of its slots, and the anchor is force-assigned to that slot even if it's normally optional — "skip this slot" is removed as a choice once an item is anchored there. This is a hard filter before generation, not a post-hoc filter.

### Tie-breaking
Sort key `(-score, sorted(item_ids))` — fully deterministic; identical requests against identical data always return identical results.

### Personalization
Request-scoped only — no persisted per-user preference table (confirmed in source, `personalization.py`). Preferred/avoided colors and "favor favorites" apply a small, capped *additive* adjustment on top of the compatibility score, kept separate so the base score's meaning never changes.

### Empty / partial wardrobes
- Empty selection → `recommendations: []` with an honest message, never a crash or fabricated outfit.
- No valid template satisfiable (e.g. only Tops, no complementary category) → `[]` + "not enough variety" message.
- A satisfiable *partial* template → outfit returned with an explicit caveat naming what's missing (e.g. "No Footwear was available... this is a partial outfit").

---

## 5. Backend

### FastAPI / REST
Python ASGI framework; routes declared with `@router.get/post/put/delete`, request/response bodies validated by Pydantic schemas. Real route list available live at `/openapi.json` or interactively at `/docs`.

### SQLAlchemy / SQLite
ORM models in `app/database/models.py`; one `sessionmaker` bound to a single SQLite file (`vistiq-backend/data/vistiq.db`). `get_db()` is a FastAPI dependency yielding one session per request, closed in a `finally` block.
**Follow-up: "What happens to the DB on a crash mid-request?"** SQLAlchemy's session `close()` rolls back any uncommitted transaction — no explicit `rollback()` calls are needed in route code for that case. The one place a *process* crash (not just a request error) could leave stale state was a try-on job stuck at "processing" — fixed by a startup sweep (`recover_interrupted_jobs`, run once in `app/main.py`'s lifespan) that marks any non-terminal job from a previous run as failed with an honest message.

### Authentication and sessions
Argon2id password hashing (`app/security/passwords.py` — the modern standard, resistant to GPU-cracking, never a hand-rolled scheme). Server-side opaque sessions in an HttpOnly cookie — the session token itself is never readable by page JavaScript. `VISTIQ_COOKIE_SECURE` controls the `Secure` cookie attribute (must be `false` for local plain-HTTP dev, `true` only once actually served over HTTPS).

### CSRF
Double-submit pattern: a `vistiq_csrf` cookie plus a matching `X-CSRF-Token` header required on every state-changing (`POST`/`PUT`/`DELETE`) route. Verified live: a request with the cookie but no header gets a 403; the real frontend always sends both.

### Ownership / isolation
Every per-resource query filters by both the resource id *and* `user_id == current_user.id` — a cross-user id and a genuinely nonexistent id are indistinguishable (plain 404 either way), so an attacker can't even confirm another user's resource exists. Verified bidirectionally, live, with two real accounts, for wardrobe items and for recommendation item-id references.

### Background jobs (try-on)
`POST /tryon` creates a DB row (`status="pending"`) and returns immediately; a FastAPI `BackgroundTask` runs the actual worker call after the response is sent. Every exit path (success / worker error / unexpected exception / process crash recovered at next startup) leaves the job in a terminal status — never permanently stuck.

---

## 6. Virtual Try-On / CatVTON

### What CatVTON is
**One-line:** An open-source diffusion-based virtual try-on model — given a photo of a person and a photo of a garment, it generates a new image of that person wearing that garment.
**Detailed:** Built on a Stable-Diffusion inpainting base model; VISTIQ does not train or fine-tune it, only runs inference against the pinned upstream repository (`Zheng-Chong/CatVTON`, commit `7818397f25613beedb3d861a34769f607cfcf3b1`).

### Diffusion models / inpainting, in one paragraph
A diffusion model learns to reverse a gradual noising process — starting from noise (or a masked region) and iteratively denoising toward a realistic image, conditioned on context (here: the person image, the garment image, and a mask of where the garment should go). "Inpainting" specifically means generating content only within a masked region while leaving the rest of the image untouched — the mechanism CatVTON uses to place a garment onto a person without regenerating their whole photo.

### Why a remote GPU worker
The dev laptop has no NVIDIA GPU; CatVTON's diffusion inference takes ~70–80 seconds per image even on a Tesla T4 and would be impractically slow (or simply unsupported) on CPU — explicitly not attempted. A separate FastAPI worker runs on Google Colab (free-tier, T4 GPU), reached from the local backend over an authenticated HTTPS tunnel (Cloudflare Quick Tunnel — temporary, no account needed, new URL each session).

### Worker authentication
Bearer token (`VISTIQ_TRYON_WORKER_TOKEN` locally / `CATVTON_WORKER_TOKEN` on the worker — same value, generated once, never committed, never printed by an automated process). The backend attaches the header server-side (`app/services/tryon_worker.py`); it never reaches the browser — verified by grepping the compiled frontend bundle.

### Known limitation (disclose proactively)
Colab's free tier has a GPU usage quota; the worker is not a permanent service. When unreachable, the app shows an honest failure message and marks the job failed — never a fabricated result. This is the single biggest outstanding gap in the project as submitted.

---

## 7. Testing and security

### Testing pyramid actually present
- **202 automated backend tests** (pytest) — authentication, session expiry, cross-user authorization on every route, the full recommendation engine (all scoring dimensions, anchor, diversity, empty/partial states), wardrobe CRUD + image cleanup, GrabCut/K-means/quality checks, try-on job lifecycle (including the crash-recovery sweep), a genuine (unmocked) classifier load + inference smoke test.
- **No frontend automated test suite** (vitest/jest) — disclosed, not hidden. Frontend verification is manual: ESLint, `tsc -b`, production build, and real browser walkthroughs.

### Security measures actually implemented
Argon2id hashing, HttpOnly + SameSite cookies, CSRF double-submit, per-request ownership filtering, path-traversal defense on every file-serving route (filename character blacklist + resolved-parent-directory check), upload content-type/size/decode validation, safe generic error messages (no stack traces or internal paths ever returned to the client — verified by a dedicated test).

### What is *not* claimed
No rate limiting, no email verification, no scheduled session cleanup (sessions are lazily invalidated on next access, not swept proactively), no production security review/pen-test, no deployment hardening — this is an honest local-development prototype, not represented as production-grade.

**Difficult follow-up: "Is this secure enough to launch as a real product?"** No, and the README says so explicitly — no rate limiting, no production HTTPS/cookie posture configured by default, no third-party security review. The *patterns* used (Argon2id, HttpOnly, CSRF, ownership filtering) are the real, correct patterns; what's missing is the operational hardening a production launch would need on top of them.
