# VISTIQ — Phase 1 Completion Report

**Engineering Foundation and Quality Assurance** — 2026-11-01

## 1. Summary of implementation

Phase 1 did not change VISTIQ's architecture, add new frameworks, or introduce
authentication. It made the existing application reproducible and testable,
corrected stale ML documentation, and completed three features that were
previously partial:

- Fixed `requirements.txt` so a fresh install actually works (missing
  Pillow/python-multipart).
- Introduced a 68-test pytest suite covering the recommendation engine, the
  wardrobe/upload API, and ML inference (mocked where expensive, plus one
  genuine unmocked model-load smoke test).
- Corrected `ml/README.md` and `models/README.md`, which both claimed the
  trained model "does not exist" — it does, and this phase independently
  verified it loads and runs correctly.
- Completed persistent favourites (was frontend-only state), anchor-item
  selection in the AI Stylist UI (backend already supported it), and safe
  image replacement in Edit Item (previously unsupported).

## 2. Files created

```
vistiq-backend/pytest.ini
vistiq-backend/requirements-dev.txt
vistiq-backend/tests/conftest.py
vistiq-backend/tests/test_recommendation_rules.py
vistiq-backend/tests/test_recommendation_engine.py
vistiq-backend/tests/test_wardrobe_api.py
vistiq-backend/tests/test_clothing_analysis_api.py
vistiq-backend/tests/test_ml_inference.py
vistiq-backend/tests/test_model_smoke.py
PHASE_1_REPORT.md
```

## 3. Files modified

```
README.md                                        (ML/testing sections corrected)
ml/README.md                                     (stale "not trained" status corrected)
models/README.md                                 (stale "not present" status corrected)
vistiq-backend/requirements.txt                   (added Pillow, python-multipart)
vistiq-backend/app/database/models.py             (added is_favorite column)
vistiq-backend/app/database/connection.py         (added idempotent column migration)
vistiq-backend/app/schemas/clothing.py            (added is_favorite to schemas)
vistiq-backend/app/routes/wardrobe.py             (image-replacement orphan cleanup)
vistiq-backend/app/services/image_validation.py   (one deprecated status-constant rename)
vistiq-frontend/src/types/clothing.ts             (added isFavorite)
vistiq-frontend/src/services/api.ts               (is_favorite wire mapping)
vistiq-frontend/src/pages/Wardrobe.tsx            (favourites now call the backend)
vistiq-frontend/src/pages/AIStylist.tsx           (anchor-item selection UI)
vistiq-frontend/src/components/EditItemModal.tsx  (photo replacement UI)
```

## 4. Dependency changes

- **`vistiq-backend/requirements.txt`**: added `Pillow==12.3.0` and
  `python-multipart==0.0.32`, pinned to the versions already verified
  working in this project. Both were previously used directly by the app
  (`PIL.Image` in `image_validation.py`; multipart form parsing for every
  `UploadFile`) but only present transitively — a fresh install was not
  guaranteed to pull them in. No other runtime dependency was touched.
- **`vistiq-backend/requirements-dev.txt`** (new, testing-only): `pytest==9.2.0`,
  `httpx==0.28.1` (required by FastAPI's `TestClient`). Does not affect the
  running application; install with
  `pip install -r requirements.txt -r requirements-dev.txt`.
- **Reproducibility verified**: installed `requirements.txt` into a brand
  new, empty virtual environment (not the existing `.venv`) and confirmed
  `from app.main import app` succeeds, with all three routers (wardrobe,
  recommendation, clothing-analysis) registered.

## 5. Tests created

68 tests across 6 files:

| File | What it covers |
|---|---|
| `test_recommendation_rules.py` | 20 pure unit tests — category/color/style/occasion/weather scoring functions, scoring-weight sanity |
| `test_recommendation_engine.py` | 14 integration tests — full candidate-generation→scoring→ranking pipeline, color/category/style/occasion/weather compatibility influencing ranking, anchor-item restriction, deterministic ranking, empty/nonexistent/insufficient-wardrobe handling, partial-outfit fallback |
| `test_wardrobe_api.py` | 17 API tests — health check, full CRUD, partial updates, 404s, image upload validation (invalid type/oversized/corrupt/empty), **new**: favourite persistence, **new**: image-replacement orphan cleanup |
| `test_clothing_analysis_api.py` | 4 API tests — success, low-confidence messaging, model-unavailable→503, invalid image rejected before the (mocked) model is ever called |
| `test_ml_inference.py` | 9 unit tests — six-category output structure, valid confidence range, low/high-confidence flagging (model mocked), real deterministic color extraction (not mocked) |
| `test_model_smoke.py` | 2 genuine tests, **not mocked** — real checkpoint loads into the real architecture with `strict=True`; real CPU inference on real uploaded photos |

Every test runs against an isolated in-memory SQLite database and a
temporary upload directory — confirmed by checking the real
`vistiq-backend/data/vistiq.db`'s size/mtime before and after a full test
run (unchanged). An earlier version of the test setup did **not** have this
isolation correctly wired for the app's startup lifespan and briefly added
the new `is_favorite` column to the real database as a side effect before
the fix — no data was lost (verified: all 29 real rows intact,
`is_favorite` correctly defaulted to 0), and this is harmless since it's
the exact migration that database needed anyway, but it's recorded here for
honesty about what happened during development.

## 6. Test execution results

```
68 passed, 12 warnings in 2.49s
```

All 68 tests pass, including the genuine (unmocked) model-load and
real-inference smoke test. The 12 warnings are all pre-existing third-party
library deprecation notices (httpx/starlette TestClient internals, an anyio
alias, Pillow's `getdata()`) — none are from VISTIQ's own code, and none
indicate a functional problem; fixing them would mean upgrading dependency
major versions, out of this phase's scope. Run with:

```powershell
cd vistiq-backend
.venv\Scripts\python.exe -m pytest -v
```

## 7. Frontend build and lint results

```
npm run lint   → clean, zero errors
npm run build  → tsc -b && vite build succeeded, 1898 modules, zero errors
```

Both ran clean after every frontend change in this phase (favourites,
anchor-item UI, image replacement).

## 8. ML model verification results

- **Resolved**: `ml/README.md` and `models/README.md` previously stated the
  trained model "does not exist" / "is not present." It exists
  (`models/vistiq_clothing_classifier.pt`, 6,234,981 bytes) and both files
  have been corrected.
- **Independently verified in this phase** (via `test_model_smoke.py`, not
  a one-off manual check): the checkpoint's `model_state_dict` loads into a
  freshly-built MobileNetV3-Small with `strict=True` (exact key/shape
  match), and a real CPU forward pass against real uploaded photos produces
  a valid category + confidence.
- **Not independently verified**: the checkpoint metadata's
  `test_accuracy: 0.9086` (90.86%) figure. This repository does not contain
  the `clothing-dataset-small` test split that number was computed against,
  and no confusion matrix / classification report / notebook output exists
  to re-derive it from. Per this phase's explicit instruction, this is
  **not** re-stated as a confirmed metric, a confusion matrix was **not**
  invented, and the documentation now says so explicitly in both
  `ml/README.md` and `models/README.md`.

## 9. Persistent favourites implementation

**Fully implemented.**

- Backend: new `is_favorite` column on `ClothingItem` (default `false`),
  exposed on `ClothingItemCreate`/`Update`/`Response`, updatable via the
  existing `PUT /wardrobe/{id}` — no new endpoint. A real, already-existing
  SQLite database (not just a fresh one) is handled automatically: `init_db()`
  now also runs a one-time `ALTER TABLE ... ADD COLUMN` if the column is
  missing, verified against a copy of the real `vistiq.db`.
- Frontend: `Wardrobe.tsx`'s local `favorites: Set<id>` state is gone;
  the heart toggle now calls `updateWardrobeItem(id, { isFavorite })` and
  applies the server-confirmed result. Survives reload because it's real
  server state, fetched the same way every other field is.
- Tested: `test_favorite_toggle_persists_across_requests` (backend);
  confirmed live against the real database via a reversible toggle
  round-trip (`PUT ... → GET ... → PUT ...` back to its original value).

## 10. Anchor-item implementation

**Fully implemented.**

- Backend already supported `selected_item_id` — untouched.
- Frontend: `AIStylist.tsx` gained a pin/unpin control on each wardrobe-pool
  item. Pinning an item sets it as the anchor (and guarantees its inclusion
  in the pool); every generated recommendation is then required to include
  it, exactly matching the existing backend contract
  (`app/recommendation/engine.py`'s `_select_templates`/`_generate_for_template`
  anchor logic, already covered by `test_anchor_item_is_present_in_every_recommendation`).
  Removing the anchor item from the pool clears the anchor rather than
  silently anchoring on an excluded item.
- Tested: backend test above; confirmed live via `POST /recommend` with
  `selected_item_id` against real wardrobe data — every returned outfit
  included the anchored item.

## 11. Image replacement implementation

**Fully implemented.**

- `EditItemModal.tsx`: a "Change Photo" control reveals the existing
  `UploadDropzone` (same client-side validation as Add Item); choosing a
  new file uploads it via the existing `POST /wardrobe/images` *before* the
  `PUT`, and the new URL is included in the update body only if a new file
  was actually chosen.
- Backend (`routes/wardrobe.py`): when a `PUT` changes `image` to a
  different value, the previous file is deleted **only after** the update
  commits successfully — reusing the existing, already path-traversal-guarded
  `delete_clothing_image()`, not a new deletion mechanism. If the upload or
  the `PUT` fails, nothing has been written to the item's record, so the
  existing photo is never at risk.
- Tested: `test_replacing_image_deletes_old_file_not_new_one` and
  `test_updating_other_fields_without_image_keeps_existing_file`.

## 12. Remaining limitations

- No frontend automated test suite (vitest/jest) — explicitly out of this
  phase's listed scope (backend pytest only).
- The 90.86% ML accuracy figure remains unverified in this repository (by
  design — not fabricated; see §8).
- No authentication (explicitly out of scope for this phase).
- No cleanup of orphaned image files for any path other than the two
  handled here (delete-item, which already existed; replace-image, added
  this phase). No cross-session consistency check that `data/uploads/`
  matches exactly what's referenced in the database.
- The one-time SQLite `ALTER TABLE` column migration is hand-written, not
  Alembic — adequate for this project's current scope (one additive column)
  but would not scale to more complex future schema changes.
- A handful of pre-existing third-party deprecation warnings remain (see §6)
  — none are VISTIQ code issues.

## 13. Git commit hash

See `git log -1 --format=fuller` on `main` immediately after this report
was committed — reported to the user directly in-session rather than
hardcoded here, since this file is itself part of that same commit.

## 14. GitHub push confirmation

Reported to the user directly in-session after `git push`, verified against
GitHub's own response (`git ls-remote`), not merely "the push command didn't
error."

## 15. Exact commands to run the updated application

```powershell
# Backend
cd vistiq-backend
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
# → http://127.0.0.1:8000 (docs at /docs)

# Backend tests
cd vistiq-backend
.venv\Scripts\python.exe -m pytest -v

# Frontend
cd vistiq-frontend
npm install
npm run dev
# → http://localhost:5173

# Frontend checks
cd vistiq-frontend
npm run lint
npm run build
```

## 16. Technical concepts to understand for the viva

- **Why a fresh `pip install` can silently work on a dev machine but fail
  elsewhere**: transitive vs. direct dependencies, and why `requirements.txt`
  must declare everything actually imported, not just top-level frameworks.
- **Dependency injection for testability**: FastAPI's `Depends(get_db)` and
  `app.dependency_overrides` — how swapping one function lets the entire
  app run against an isolated in-memory database with zero route code
  changes.
- **Why `StaticPool` + `sqlite:///:memory:`**: a plain in-memory SQLite
  database is per-connection; `StaticPool` keeps one connection alive for
  the whole test so every query sees the same data.
- **Mocking vs. integration testing**: why `/analyze-clothing`'s PyTorch
  call is mocked in ordinary API tests (speed, determinism) but still has
  one deliberately unmocked smoke test (`test_model_smoke.py`) — the
  difference between "does the API wiring work" and "does the real model
  actually work."
- **`strict=True` state_dict loading**: why an exact key/shape match
  between a saved checkpoint and a freshly-built model architecture is
  meaningful evidence the file is genuine, not just "a file that exists."
- **Additive-only SQLite migration**: why `ALTER TABLE ADD COLUMN` is safe
  without a full migration framework for one new nullable-with-default
  column, and why it would *not* be safe for renaming/removing columns.
- **Idempotent server-side cleanup**: why the image-replacement delete only
  happens after a successful commit, and why `delete_clothing_image()`
  never raises — be ready to explain the failure modes this protects
  against (partial writes, orphaned files, a delete racing a later read).
