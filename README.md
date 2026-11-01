# VISTIQ — AI Wardrobe Recommendation System

## 1. What VISTIQ is

VISTIQ is a personal wardrobe management and outfit recommendation web application. A user digitizes their real clothing items into a personal database, then asks VISTIQ to recommend complete outfits for a given occasion, style preference, and weather context.

## 2. Problem being solved

The original brief for this project criticized an early prototype as follows:

> "The system is only searching/filtering clothes from a database and is not actually recommending."

VISTIQ addresses this directly. Rather than letting a user filter/search their own wardrobe by tags, the backend performs the recommendation itself: it generates multiple candidate outfit combinations from the user's wardrobe pool, scores each candidate against six weighted compatibility dimensions, ranks them, and returns the top-K with a human-readable explanation of *why* each outfit was chosen — the same architecture a genuine recommender system uses, not a filtered list.

## 3. How VISTIQ recommends outfits

For a given request (occasion, optional style, optional weather, a wardrobe item pool, optional "anchor" item, and `top_k`):

1. **Candidate generation** — the wardrobe pool is grouped by category (Tops, Bottoms, Outerwear, Dresses, Footwear, Accessories) and matched against a set of outfit templates (e.g. Top+Bottom+Footwear, Dress+Footwear). Every valid combination of items across the matching templates is generated as a candidate outfit.
2. **Compatibility scoring** — each candidate is scored 0–100 from six weighted components: color compatibility (30%), category compatibility (20%), style compatibility (20%), occasion fit (15%), user wear-history preference (10%), and weather/season fit (5%).
3. **Ranking** — all candidates are sorted by score (descending), with a deterministic tiebreaker so identical requests always return identical results.
4. **Explanation** — each returned outfit includes a natural-language reason derived directly from which scoring components were actually high for that specific outfit (not a generic message).
5. **Anchoring** — a user can select one specific wardrobe item; every returned outfit is guaranteed to include it, and the recommendation set changes when the anchor changes.

This is a rule-based, fully explainable, deterministic recommendation engine — not a database filter, and not (yet) a learned ranking model.

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
- **Pages:** Home (`/`), My Wardrobe (`/wardrobe`), Add Item (`/add-item`), AI Stylist (`/stylist`), Recommendations (`/recommendations`).
- **Design source:** Stitch reference designs under `Stitch/` (read-only reference — never modified by the app code).
- All backend communication goes through a single client module, `src/services/api.ts`, which translates between the app's camelCase types and the backend's snake_case wire format.

## 6. Backend

- **Stack:** FastAPI + Uvicorn, Python 3.12.
- **Routes:**
  - `GET /`, `GET /health` — service status
  - `GET /wardrobe`, `POST /wardrobe`, `GET /wardrobe/{id}`, `PUT /wardrobe/{id}`, `DELETE /wardrobe/{id}` — wardrobe CRUD
  - `POST /wardrobe/images` — uploads a photo to local disk storage, returns its servable URL (see §7)
  - `POST /recommend` — outfit recommendation
  - `POST /analyze-clothing` — ML clothing image analysis (see §9)
- `GET /uploads/<filename>` — serves stored wardrobe photos (`StaticFiles` mount, backed by `vistiq-backend/data/uploads/`).
- CORS is restricted to the local Vite dev origins (`http://localhost:5173`, `http://127.0.0.1:5173`).

## 7. Database & image storage

- SQLite, via SQLAlchemy ORM, file at `vistiq-backend/data/vistiq.db`.
- Single table `clothing_items`: id, name, category, subcategory, color, secondary_color, style, occasion, season, gender, image, description, wear_count, created_at.
- Tables are created automatically on backend startup (`init_db()`); no manual migration step is required for this project's scope.
- **Wardrobe photos** are stored as local files under `vistiq-backend/data/uploads/`, not as base64 blobs in SQLite. Add Item uploads the photo to `POST /wardrobe/images` (`app/services/image_storage.py`), which validates it (same checks as `/analyze-clothing`: JPEG/PNG/WEBP only, 10MB max, must actually decode as an image), saves it under a random server-generated filename — the original filename is never trusted or used — and returns a relative URL (e.g. `/uploads/<uuid>.jpg`). That URL is what's stored in `clothing_items.image` and what `GET /uploads/...` (a `StaticFiles` mount in `app/main.py`) serves back. Files on disk are independent of the running process, so uploaded photos survive both a page refresh and a full backend restart.

## 8. Recommendation engine

Implemented in `vistiq-backend/app/recommendation/`:
- `rules.py` — pure, deterministic compatibility functions (color pair harmony, category complementarity, style compatibility, occasion matching, weather/season matching). No side effects, no database access.
- `scoring.py` — combines the rule outputs into a single weighted 0–100 score per candidate outfit using the weights in §3.
- `engine.py` — candidate generation from outfit templates, deduplication, scoring, ranking, and explanation generation.

The engine is intentionally free of randomness: the same request against the same database state always returns the same result.

## 9. ML component — clothing image analysis

**Status: trained and integrated.** The model was trained in Google Colab and the exported checkpoint is loaded and used by the live backend.

- **Architecture:** MobileNetV3-Small (torchvision, ImageNet-pretrained backbone), two-phase transfer learning — freeze backbone and train a new classification head, then unfreeze the last few backbone blocks and fine-tune at a low learning rate.
- **Dataset:** `clothing-dataset-small` (Alexey Grigorev, CC0), whose 10 real-world classes are mapped onto VISTIQ's 6 wardrobe categories — mapping documented in `ml/labels/clothing_categories.json` and `ml/README.md`.
- **Test accuracy: 90.86%**, measured on 372 held-out test images that were never used for training. Precision/recall/F1 per class and a confusion matrix were also produced during evaluation (see the Colab notebook's own output — not re-derived or re-verified locally).
- **Training environment:** Google Colab (GPU). Training was **not** run on the local development machine, which has no NVIDIA GPU. Notebook: `ml/notebooks/vistiq_clothing_classifier_colab.ipynb`.
- **Checkpoint:** `models/vistiq_clothing_classifier.pt` (~6MB) — a metadata-wrapped checkpoint (`model_state_dict`, `categories`, `num_classes`, `image_size`, `architecture`, `test_accuracy`). `ml/training/model.py`'s `load_model()` unwraps `model_state_dict` before loading it into the unmodified MobileNetV3-Small architecture — this was the one compatibility fix required to load the real export format; no retraining, no architecture change.
- **Inference:** `ml/inference/predict.py` exposes `predict_clothing(image)`. Runs on **CPU only** — verified end-to-end, no GPU/CUDA involved. On real held-out sample images, correctly predicted "Tops" (57.1% confidence, correctly flagged as low-confidence and worth reviewing), "Bottoms" (99.8%), and "Footwear" (99.99%).
- **Color detection — user-confirmed, not authoritative:** dominant-color extraction (`ml/inference/color.py`) is deterministic image processing (palette quantization + nearest-neighbor match to a fixed VISTIQ color list), **not** a second ML model, and testing showed it is not reliably foreground-aware — it can pick up background or secondary pattern colors instead of the garment's true color (e.g. a black-and-white patterned garment on a light background was suggested as "Navy"). Because of this, the color extraction is surfaced in the Add Item flow only as a *suggestion* ("Suggested color — please confirm"), pre-filling the color picker without ever being silently trusted; the value actually saved to the wardrobe database, and used by the recommendation engine, is always whatever the user confirms or corrects. `color_confidence` is always `null` in the API response to keep this distinct from the real ML category confidence.
- **`POST /analyze-clothing`:** implemented, integration-tested with the real trained model, and still has a graceful `503 Service Unavailable` fallback (never a crash) if the checkpoint file is ever absent.
- **Frontend integration:** implemented in Add Item — uploading a photo calls `/analyze-clothing`, pre-fills category and color as clearly-labeled suggestions ("AI predicted — please review" / "Suggested color — please confirm"), shows the real confidence, and flags low-confidence predictions (<60%) for review — the user can freely correct either field before saving, and saving is never blocked by low confidence.

If the checkpoint is ever missing, retrain via the Colab notebook and place the exported file at `models/vistiq_clothing_classifier.pt`.

## 10. How to run the frontend

```powershell
cd vistiq-frontend
npm install
npm run dev
```

Serves at `http://localhost:5173`.

## 11. How to run the backend

```powershell
cd vistiq-backend
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Serves at `http://127.0.0.1:8000`. Interactive API docs at `/docs`.

## 12. Testing

The system has been manually integration-tested end-to-end, including with the real trained model: frontend build/lint, backend startup and every route, full wardrobe CRUD cycle, image upload/persistence across page refresh and backend restart, the recommendation engine under varying occasion/style/weather/anchor/top_k parameters (including the empty-state path when a wardrobe pool has no valid category combination), real CPU inference through `/analyze-clothing`, and a real browser walkthrough of Home → Add Item (upload → AI prediction → user review/correction → save) → My Wardrobe (real photo visible) → AI Stylist → Recommendations, including changing occasion and confirming the recommendation actually changes. See the Stage 14, 15, and 16 test reports for full results tables. There is no automated test suite (e.g. pytest/vitest) yet — testing so far has been manual, targeted integration verification, not a CI-run regression suite.

## 13. Current limitations

- Automatic color extraction is not reliably foreground-aware (it can pick up background/secondary colors) — it is intentionally treated as a suggestion only; the user-confirmed color is what's actually saved and scored. See §9.
- The AI Stylist UI does not yet expose anchor-item selection (`selected_item_id`), even though the backend recommendation API supports it and it has been verified working directly against the API.
- No automated test suite (pytest/vitest) — verification has been manual/scripted integration testing.
- No authentication — single implicit user, no accounts or multi-user isolation.
- No deployment configuration — local development only.
- Uploaded photos are stored locally on disk (`vistiq-backend/data/uploads/`) with no size cap on the directory as a whole and no cleanup of orphaned files if a wardrobe item is later deleted — acceptable for a local PBL prototype, not for production use.

## 14. Future scope

- Improve color extraction (e.g. a segmentation-aware or garment-focused crop) to the point it could reasonably be promoted from "suggestion" to a trusted default.
- Expose anchor-item selection in the AI Stylist UI.
- Add an automated backend (pytest) and frontend (vitest) test suite.
- Expand the recommendation engine's color/style rule tables as more real wardrobe data becomes available.
- Delete the associated uploaded file when a wardrobe item with an image is deleted.
- User accounts and multi-user wardrobes.
