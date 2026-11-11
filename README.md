# VISTIQ — AI Wardrobe Recommendation System

## 1. What VISTIQ is

VISTIQ is a personal wardrobe management and outfit recommendation web application. A user digitizes their real clothing items into a personal database, then asks VISTIQ to recommend complete outfits for a given occasion, style preference, and weather context.

## 2. Problem being solved

The original brief for this project criticized an early prototype as follows:

> "The system is only searching/filtering clothes from a database and is not actually recommending."

VISTIQ addresses this directly. Rather than letting a user filter/search their own wardrobe by tags, the backend performs the recommendation itself: it generates multiple candidate outfit combinations from the user's wardrobe pool, scores each candidate against six weighted compatibility dimensions, ranks them, and returns the top-K with a human-readable explanation of *why* each outfit was chosen — the same architecture a genuine recommender system uses, not a filtered list.

## 3. How VISTIQ recommends outfits

For a given request (occasion, optional style, optional weather, a wardrobe item pool, optional "anchor" item, optional personalization preferences, and `top_k`):

1. **Candidate generation** — the wardrobe pool is grouped by category (Tops, Bottoms, Outerwear, Dresses, Footwear, Accessories) and matched against a set of outfit templates (e.g. Top+Bottom+Footwear, Dress+Footwear). Every valid combination of items across the matching templates is generated as a candidate outfit — this doubles as the engine's hard constraint filter (a template's required categories must all be present; an anchor item must be structurally includable), so an invalid combination is never generated at all, not generated-then-rejected.
2. **Compatibility scoring** — each candidate is scored 0–100 from six weighted components: color compatibility (30%), category compatibility (20%), style compatibility (20%), occasion fit (15%), user wear-history preference (10%), and weather/season fit (5%). Color compatibility uses real color theory — hue-wheel relationships (complementary/analogous/monochromatic), VISTIQ's established classic/neutral pairings, each item's optional secondary color, and down-weighting when an item's photo-analyzed color reliability was low — not just a lookup table (see `app/recommendation/color_theory.py`).
3. **Personalization** — optional, request-scoped preferences (preferred/avoided colors, favoring favorited items) apply a small, capped adjustment on top of the compatibility score. No accounts, nothing persisted — every preference lives only on that one request.
4. **Ranking** — all candidates are sorted by the (personalization-adjusted) score, descending, with a deterministic tiebreaker so identical requests always return identical results.
5. **Diversity-aware selection** — a greedy, Jaccard-overlap reranking (a simple, deterministic form of Maximal Marginal Relevance) reduces near-duplicate outfits among the top results, without ever promoting a lower-scoring outfit purely for being different — the single best-scored outfit is always returned first. Can be disabled per-request (`diversify: false`).
6. **Explanation** — each returned outfit includes both a natural-language reason and a structured breakdown (per-dimension scores, specific positive reasons, and honest caveats such as low color-extraction reliability or a partial outfit) derived directly from which scoring components were actually high for that specific outfit — never a generic or invented reason.
7. **Anchoring** — a user can select one specific wardrobe item; every returned outfit is guaranteed to include it (through every stage above, including diversity selection), and the recommendation set changes when the anchor changes. If no valid outfit can include the anchor, the response explains that specifically.

This is a deterministic, rule-based, fully explainable hybrid recommendation engine — not a database filter, and not a learned ranking model.

## 4. System architecture

```
User
  |
Frontend (React + Vite, Stitch-designed UI)
  |
Backend API (FastAPI)
  |
ML Clothing Analysis
  |  MobileNetV3-Small -> category + confidence (real ML, 90.86% test accuracy)
  |  deterministic color extraction -> suggested color (user must confirm/correct)
  |
Wardrobe Database (SQLite via SQLAlchemy, user-confirmed attributes) + local image files (data/uploads/)
  |
Recommendation Engine (rule-based: candidate generation -> scoring -> ranking -> explanation)
  |
Ranked Outfit Recommendations
  |
Frontend
```

## 5. Frontend

- **Stack:** React 19 + TypeScript + Vite + Tailwind CSS, `react-router-dom` for routing.
- **Pages:** Home (`/`, public), Login (`/login`, public), Register (`/register`, public), My Wardrobe (`/wardrobe`), Add Item (`/add-item`), AI Stylist (`/stylist`), Recommendations (`/recommendations`) — the last four require a logged-in session (`src/components/ProtectedRoute.tsx`), which is restored automatically on page refresh via `GET /auth/me` (`src/context/AuthContext.tsx`).
- **Design source:** Stitch reference designs under `Stitch/` (read-only reference — never modified by the app code).
- All backend communication goes through a single client module, `src/services/api.ts`, which translates between the app's camelCase types and the backend's snake_case wire format, sends cookies on every request (`credentials: "include"`), and attaches the CSRF header on state-changing requests.

## 6. Backend

- **Stack:** FastAPI + Uvicorn, Python 3.12.
- **Routes:**
  - `GET /`, `GET /health` — service status
  - `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` — authentication (see §7)
  - `GET /wardrobe`, `POST /wardrobe`, `GET /wardrobe/{id}`, `PUT /wardrobe/{id}`, `DELETE /wardrobe/{id}` — wardrobe CRUD, scoped to the authenticated user
  - `POST /wardrobe/images` — uploads a photo to local disk storage, returns its servable URL (see §8)
  - `GET /wardrobe/images/{filename}` — serves a stored photo, only to the user who owns the item it's attached to (see §8)
  - `POST /recommend` — outfit recommendation, from the authenticated user's wardrobe only
  - `POST /analyze-clothing` — ML clothing image analysis (see §10)
  - `POST /tryon`, `GET /tryon`, `GET /tryon/{id}`, `GET /tryon/results/{filename}`, `DELETE /tryon/{id}` — virtual try-on jobs, experimental (see §16)
- Every route above except `/`, `/health`, `/auth/register`, and `/auth/login` requires a valid session; every state-changing route (`POST`/`PUT`/`DELETE`) additionally requires the CSRF header described in §7.
- CORS is restricted to the local Vite dev origins (`http://localhost:5173`, `http://127.0.0.1:5173`), with `allow_credentials=True` (required for the session cookie to work cross-port in local dev).

## 7. Authentication

- **Password storage:** Argon2id (`argon2-cffi`), via `app/security/passwords.py` — never plaintext, never a reversible encryption, never a hand-rolled hash. A fresh random salt per password is generated automatically by the library.
- **Sessions:** an opaque, cryptographically random token (`secrets.token_urlsafe`), stored in an `HttpOnly` cookie. Only a SHA-256 hash of the token is ever written to the database (`app/security/sessions.py`) — a stolen database can't be turned back into a valid session. A brand-new session is created on every login (rotation — the standard defense against session fixation), and sessions expire after 7 days.
- **Cookies:** `HttpOnly` always; `SameSite=Lax`; `Secure` is controlled by the `VISTIQ_COOKIE_SECURE` environment variable (see `vistiq-backend/.env.example`) — `false` for local HTTP dev (a `Secure` cookie is silently dropped over plain HTTP), set to `true` in any real HTTPS deployment.
- **CSRF:** a double-submit cookie — a second, non-`HttpOnly` `vistiq_csrf` cookie, which the frontend reads and echoes back as an `X-CSRF-Token` header on every state-changing request (`vistiq-frontend/src/services/api.ts`). Checked server-side (`app/security/dependencies.py:require_csrf`) on every `POST`/`PUT`/`DELETE` route except `/auth/register` and `/auth/login`, which have no prior session to protect.
- **Ownership:** every wardrobe/recommendation query is filtered by the authenticated user's id (never a user id supplied in the request body). A cross-user access attempt and a genuinely nonexistent id both return a plain 404 — the API never confirms that a private item exists for someone else.
- **Known limitation:** no scheduled cleanup job for expired sessions (they're deleted lazily, on the next access attempt that finds them expired) — acceptable at this project's scale.

## 8. Database & image storage

- SQLite, via SQLAlchemy ORM, file at `vistiq-backend/data/vistiq.db`.
- Tables: `users` (id, name, email, password_hash, created_at), `user_sessions` (id, user_id, token_hash, created_at, expires_at), and `clothing_items`: id, user_id, name, category, subcategory, color, secondary_color, style, occasion, season, gender, image, description, wear_count, is_favorite, color_reliability, created_at.
- Tables are created automatically on backend startup (`init_db()`); additive column migrations (e.g. `user_id`) are applied by hand via `ALTER TABLE` — no Alembic in this project's scope. **Pre-authentication wardrobe rows have `user_id = NULL`** — preserved on disk, never deleted, but permanently unreachable through the user-scoped API (by design — see `app/database/models.py`'s `ClothingItem.user_id` docstring).
- **Wardrobe photos** are stored as local files under `vistiq-backend/data/uploads/`, not as base64 blobs in SQLite. Add Item uploads the photo to `POST /wardrobe/images` (`app/services/image_storage.py`), which validates it (same checks as `/analyze-clothing`: JPEG/PNG/WEBP only, 10MB max, must actually decode as an image), saves it under a random server-generated filename — the original filename is never trusted or used — and returns a relative URL (e.g. `/wardrobe/images/<uuid>.jpg`). That URL is what's stored in `clothing_items.image` and what `GET /wardrobe/images/<filename>` (an authenticated, ownership-checked route — **not** a public static file mount) serves back. Files on disk are independent of the running process, so uploaded photos survive both a page refresh and a full backend restart.

## 9. Recommendation engine

Implemented in `vistiq-backend/app/recommendation/`:
- `rules.py` — pure, deterministic compatibility functions (category complementarity, style compatibility, occasion matching, weather/season matching), unchanged since Phase 1 and still directly unit-tested on their own.
- `color_theory.py` — color compatibility via HSV hue-wheel relationships (complementary/analogous/monochromatic/contrasting) over VISTIQ's existing 14-color named palette, falling back to `rules.py`'s proven classic/neutral pairings first; blends in each item's optional secondary color; down-weights a pair's score when either item's stored `color_reliability` is "medium"/"low" (an unknown reliability is never treated as a known-bad one).
- `scoring.py` — combines color/category/style/occasion/weather/preference into a single weighted 0–100 score per candidate outfit (weights in §3), plus the evidence (e.g. which color relationships were found) used for explanations.
- `personalization.py` — optional, request-scoped preference adjustments (preferred/avoided colors, favorite items) — no accounts, nothing persisted.
- `diversity.py` — greedy, Jaccard-overlap reranking to reduce near-duplicate outfits among the results.
- `engine.py` — candidate generation from outfit templates, deduplication, scoring, personalization, diversity selection, and structured explanation generation.

The engine is intentionally free of randomness: the same request against the same database state always returns the same result.

## 10. ML component — clothing image analysis

**Status: trained and integrated.** The model was trained in Google Colab and the exported checkpoint is loaded and used by the live backend.

- **Architecture:** MobileNetV3-Small (torchvision, ImageNet-pretrained backbone), two-phase transfer learning — freeze backbone and train a new classification head, then unfreeze the last few backbone blocks and fine-tune at a low learning rate.
- **Dataset:** `clothing-dataset-small` (Alexey Grigorev, CC0), whose 10 real-world classes are mapped onto VISTIQ's 6 wardrobe categories — mapping documented in `ml/labels/clothing_categories.json` and `ml/README.md`.
- **Test accuracy: 90.86%**, measured on 372 held-out test images that were never used for training. Precision/recall/F1 per class and a confusion matrix were also produced during evaluation (see the Colab notebook's own output — not re-derived or re-verified locally).
- **Training environment:** Google Colab (GPU). Training was **not** run on the local development machine, which has no NVIDIA GPU. Notebook: `ml/notebooks/vistiq_clothing_classifier_colab.ipynb`.
- **Checkpoint:** `models/vistiq_clothing_classifier.pt` (~6MB) — a metadata-wrapped checkpoint (`model_state_dict`, `categories`, `num_classes`, `image_size`, `architecture`, `test_accuracy`). `ml/training/model.py`'s `load_model()` unwraps `model_state_dict` before loading it into the unmodified MobileNetV3-Small architecture — this was the one compatibility fix required to load the real export format; no retraining, no architecture change. Independently verified (not just assumed) by the automated test suite: `vistiq-backend/tests/test_model_smoke.py` loads this exact checkpoint with `strict=True` and runs a real inference pass against real uploaded photos.
- **Inference:** `ml/inference/predict.py` exposes `predict_clothing(image)`. Runs on **CPU only** — verified end-to-end, no GPU/CUDA involved. On real held-out sample images, correctly predicted "Tops" (57.1% confidence, correctly flagged as low-confidence and worth reviewing), "Bottoms" (99.8%), and "Footwear" (99.99%).
- **Color detection — user-confirmed, not authoritative:** two layers, both classical image processing, **neither** a second ML model (see `ml/README.md`'s "Color extraction (not ML)" section for the full detail). The primary path is GrabCut foreground segmentation (`ml/inference/segmentation.py`) + K-means color clustering over HSV (`ml/inference/color_advanced.py`), which reduces — but does not eliminate — the background-color leakage the original simpler method had; it falls back automatically to that original deterministic method (`ml/inference/color.py`) whenever segmentation or clustering can't produce a trustworthy result. Either way, color extraction is surfaced in the Add Item flow only as a *suggestion* ("Suggested color — please confirm"), pre-filling the color picker without ever being silently trusted; the value actually saved to the wardrobe database, and used by the recommendation engine, is always whatever the user confirms or corrects. `color_confidence` is a real (non-ML) cluster-dominance score when the primary path succeeds, and `null` when it fell back — never a machine-learning confidence value either way.
- **`POST /analyze-clothing`:** implemented, integration-tested with the real trained model, has a graceful `503 Service Unavailable` fallback (never a crash) if the checkpoint file is ever absent, and a `400 Bad Request` if the uploaded image is too small to analyze reliably (below 32px either side).
- **Frontend integration:** implemented in Add Item — uploading a photo calls `/analyze-clothing`, pre-fills category and color as clearly-labeled suggestions ("AI predicted — please review" / "Suggested color — please confirm"), shows the real confidence, and flags low-confidence predictions (<60%) for review — the user can freely correct either field before saving, and saving is never blocked by low confidence.

If the checkpoint is ever missing, retrain via the Colab notebook and place the exported file at `models/vistiq_clothing_classifier.pt`.

## 11. How to run the frontend

```powershell
cd vistiq-frontend
npm install
npm run dev
```

Serves at `http://localhost:5173`.

## 12. How to run the backend

```powershell
cd vistiq-backend
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Serves at `http://127.0.0.1:8000`. Interactive API docs at `/docs`. Copy `.env.example` to `.env` to override `VISTIQ_COOKIE_SECURE` (see §7) — the default (`false`) is already correct for this local setup.

## 13. Testing

The system has been manually integration-tested end-to-end, including with the real trained model: frontend build/lint, backend startup and every route, full wardrobe CRUD cycle, image upload/persistence across page refresh and backend restart, the recommendation engine under varying occasion/style/weather/anchor/top_k parameters (including the empty-state path when a wardrobe pool has no valid category combination), real CPU inference through `/analyze-clothing`, and a real browser walkthrough of Home → Add Item (upload → AI prediction → user review/correction → save) → My Wardrobe (real photo visible) → AI Stylist → Recommendations, including changing occasion and confirming the recommendation actually changes. See the Stage 14, 15, and 16 test reports for full results tables.

**Automated tests:** `vistiq-backend/tests/` — a pytest suite covering authentication (registration, login/logout, session expiry/invalidation, password hashing), cross-user authorization (every wardrobe/recommendation/image endpoint, confirmed un-reachable by a second user), the recommendation engine (candidate generation, all six scoring dimensions, anchor restriction, deterministic ranking, empty/insufficient-wardrobe handling), the wardrobe CRUD API, image upload validation, GrabCut segmentation + K-means color extraction + image-quality checks, and ML inference (mocked for speed in ordinary tests, plus one genuine unmocked model-load + real-inference smoke test). Run with `cd vistiq-backend && .venv\Scripts\python.exe -m pytest`. There is still no frontend automated test suite (vitest/jest) — frontend verification remains manual build/lint + browser walkthrough.

## 14. Current limitations

- Automatic color extraction is improved but still not perfectly foreground-aware — GrabCut segmentation (see §10, `ml/README.md`) assumes a roughly centered garment with background nearer the edges, and can fail on off-center photos or backgrounds close in color to the garment; it is intentionally treated as a suggestion only either way, and the user-confirmed color is what's actually saved and scored. See §10.
- Backend now has an automated pytest suite (Phase 1); the frontend still has no automated test suite (vitest/jest) — its verification remains manual/scripted integration testing.
- No deployment configuration — local development only; no production security review has been performed, and VISTIQ should not be treated as production-ready as-is (see §7's cookie/CSRF notes and the no-scheduled-session-cleanup limitation).
- Uploaded photos are stored locally on disk (`vistiq-backend/data/uploads/`) with no size cap on the directory as a whole and no cleanup of orphaned files if a wardrobe item is later deleted — acceptable for a local PBL prototype, not for production use.
- Login/register are not behind CSRF protection (standard practice — there's no prior session to protect at that point), which leaves a low-severity "login CSRF" theoretical gap.

## 15. Future scope

- Color extraction is now segmentation-aware (GrabCut + K-means, see §10) but still not reliable enough to promote from "suggestion" to a trusted default — a learned, garment-aware segmentation model would be the next step if that's ever needed.
- Add an automated frontend (vitest) test suite (backend pytest suite added in Phase 1).
- Expand the recommendation engine's color/style rule tables as more real wardrobe data becomes available.
- A scheduled cleanup job for expired sessions, rather than today's lazy (on-next-access) deletion.
- A way to reclaim the pre-authentication legacy wardrobe rows (`user_id = NULL`) — currently preserved but permanently unreachable through the API by design (see §8).

## 16. Virtual Try-On (Phase 5, experimental)

A user can see one of their own wardrobe garments rendered onto a photo of themselves, via [CatVTON](https://github.com/Zheng-Chong/CatVTON) — a real diffusion-based virtual try-on model. Genuine CatVTON inference was verified (sample runs with real GPU timings and VRAM measurements, visually correct results), and the full job lifecycle (authenticated creation, ownership-scoped status/result/delete, CSRF, input validation, error handling) is implemented and automated-test-covered (`vistiq-backend/tests/test_tryon_api.py`, `test_tryon_worker.py`). VISTIQ's backend has no GPU and calls out to a separate worker over an authenticated (bearer token) HTTP connection (`app/services/tryon_worker.py`); with none configured, a try-on job is still created for real but immediately and honestly marked "failed: unavailable," never faked as a success. This repository does not ship or deploy a permanent worker — §9 of the docs below covers a real GPU worker that was run in Google Colab, exposed over a temporary authenticated HTTPS tunnel, connected to this backend, and driven end-to-end through the actual browser UI (including a two-account isolation check), which is the closest verification short of a standing deployment. An 8-sample real-world visual quality evaluation (§10) — real human and garment photographs, run through the actual app, scored on garment preservation/pose/background/realism/artifacts — found 8/8 technical success and 6/8 visually convincing results; the other 2 are disclosed honestly, not hidden (one rendering artifact, one caused by a cropped source photo, not by CatVTON itself). CatVTON's fine-tuned weights are CC BY-NC-SA 4.0 (non-commercial) — this feature is a research proof of concept, not cleared for commercial use as-is.

Full detail — exact verified dependency versions (several deviate from CatVTON's own `requirements.txt` for documented reasons), the real inference numbers, the worker HTTP contract and bearer-auth setup, the temporary tunnel connection, the Phase 5.3 evaluation methodology and results, licensing, and how to reproduce the Colab run — is in **[`docs/virtual-tryon.md`](docs/virtual-tryon.md)**.

Frontend: `vistiq-frontend/src/pages/TryOn.tsx`, routed at `/try-on`. Backend: `vistiq-backend/app/routes/tryon.py`, `app/services/tryon_worker.py`, `app/services/tryon_storage.py`, `app/database/models.py:TryOnJob`.
