# VISTIQ Machine Learning Workspace (Stage 13)

Real, trained image understanding for VISTIQ's Add Clothing flow:

```
user uploads clothing photo
        ↓
image quality check (resolution/blur/exposure — warn, don't block; Phase 2)
        ↓
MobileNetV3-Small classifier (trained via transfer learning)
        ↓
predicted VISTIQ category + confidence
        ↓
GrabCut foreground segmentation, with a deterministic fallback (Phase 2,
classical image processing, not ML)
        ↓
K-means color clustering over the (foreground-aware) pixels, with a
deterministic fallback to the original Phase 1 method (Phase 2, classical
image processing, not ML)
        ↓
primary + secondary color, pattern, brightness, reliability indicator
        ↓
shown to the user for review before saving to the wardrobe
```

The existing rule-based recommendation engine (`vistiq-backend/app/recommendation/`)
is **not** replaced or touched by this. ML identifies a garment; the existing
engine still decides how garments go together.

## Status

**Trained and verified.** `models/vistiq_clothing_classifier.pt` exists and
has been independently verified in this repository (not just assumed from
the checkpoint's own metadata):

- The checkpoint loads as a `dict` with `model_state_dict` +
  export metadata (`categories`, `num_classes`, `image_size`, `architecture`,
  `test_accuracy`), and `ml/training/model.py`'s `load_model()` loads that
  `model_state_dict` into a freshly-built MobileNetV3-Small with
  `strict=True` — zero missing/unexpected keys, zero shape mismatches
  (verified by `vistiq-backend/tests/test_model_smoke.py`, which fails the
  test suite if this ever stops being true).
- A real forward pass through the real checkpoint on a real uploaded photo
  produces a prediction (category + confidence) — also exercised by
  `test_model_smoke.py`, not a fabricated or hand-written example.
- **The embedded `test_accuracy: 0.9086` (90.86%) figure is *previously
  reported*, not independently reproduced in this repository.** No
  evaluation artifacts (confusion matrix, classification report, or
  notebook cell outputs) are present here to re-derive it from — the
  `clothing-dataset-small` test split this number was computed against is
  not stored in this repo (it's cloned separately into Colab per the
  dataset section below), and the committed copy of
  `ml/notebooks/vistiq_clothing_classifier_colab.ipynb` has empty cell
  outputs. Treat 90.86% as the training run's own self-reported number,
  plausible given the model genuinely passes the strict architecture/weight
  checks above, but not something this repository can currently prove on
  its own. If you want it independently reproduced: clone
  `clothing-dataset-small` into the path `ml/training/dataset.py` expects,
  then run `ml/training/evaluate.py`'s `evaluate_model()` against the real
  test split and commit the resulting report alongside this file.

## Hardware constraint

The development laptop has no NVIDIA GPU. Training therefore happens in
**Google Colab** (`ml/notebooks/vistiq_clothing_classifier_colab.ipynb`),
never locally. The laptop only ever runs **CPU inference** against an
already-trained model exported from Colab.

## Dataset

**[clothing-dataset-small](https://github.com/alexeygrigorev/clothing-dataset-small)**
by Alexey Grigorev — CC0 (public domain).

- Real photographed clothing images (not the tiny 28×28 grayscale
  Fashion-MNIST images from the earlier version of this project — that
  dataset is explicitly not used here, per the project's own instruction
  that it isn't representative of real wardrobe photos).
- A pre-split (`train/` / `validation/` / `test/`) subset covering the 10
  most common classes from the larger `clothing-dataset-full` (5,000+
  images). Small enough to train in a reasonable time in Colab.
- No Kaggle account/API key needed — just `git clone`.
- **Verified directly against the live repository** (via the GitHub API,
  `contents` and `contents/train` endpoints) before writing the label
  mapping below, rather than assumed from memory. The 10 confirmed class
  folders: `dress, hat, longsleeve, outwear, pants, shirt, shoes, shorts,
  skirt, t-shirt`.

Exact image counts per class/split are **not fabricated here** — the
notebook's "Dataset inspection" section computes and prints the real counts
the first time it's run, since that number depends on what's actually in the
repo at clone time.

## Label mapping (dataset → VISTIQ)

Defined once, as data, in `ml/labels/clothing_categories.json` — loaded by
`ml/training/config.py` so every script (dataset loading, training,
evaluation, inference, FastAPI) uses the exact same mapping.

| Dataset folder | VISTIQ category |
|---|---|
| t-shirt, shirt, longsleeve | **Tops** |
| pants, shorts, skirt | **Bottoms** |
| outwear | **Outerwear** |
| dress | **Dresses** |
| shoes | **Footwear** |
| hat | **Accessories** |

**Documented limitation:** `Outerwear` and `Accessories` each map from only
*one* narrow source class (`outwear`, `hat` respectively). The trained
model's notion of "Accessories" will really only mean "hat-like images" —
it will not recognize bags, jewelry, belts, etc. This is a genuine dataset
limitation, not glossed over. `ml/README.md`'s evaluation section (once
training happens) will report per-class metrics so this weakness is visible
in real numbers, not hidden.

## Model architecture

**MobileNetV3-Small**, ImageNet-pretrained, via `torchvision`.

Why (see `ml/training/model.py` for the full rationale in code comments):
1. Lightweight — ~2.5M parameters, fast to fine-tune and fast for CPU inference.
2. Pretrained — already has useful general visual features before seeing any
   clothing photos.
3. Small enough to explain end-to-end in a viva: "a pretrained feature
   extractor plus a small classifier head we trained ourselves."
4. Easy to integrate — plain `torch`/`torchvision`, no exotic runtime needed
   in FastAPI.

Training strategy — two-phase transfer learning (`ml/training/train.py`):
- **Phase 1:** freeze the entire pretrained backbone; train only the new
  6-class classification head (fast, stabilizes the new layer first).
- **Phase 2:** unfreeze the last few backbone blocks; fine-tune everything
  unfrozen at a much lower learning rate, so pretrained low-level features
  aren't destroyed while higher-level features adapt to clothing photos.
- Early stopping on validation accuracy + checkpointing the best weights
  seen, so a run that starts overfitting doesn't overwrite a better epoch.

## Color extraction (not ML)

Neither of the two pipelines below is machine learning. There is no
training, no learned weights, and no dataset involved in either — both are
classical, deterministic image-processing techniques, kept clearly
separate from the trained MobileNetV3 classifier above.

**Phase 1 (original, still present as the fallback):**
`ml/inference/color.py` — Pillow palette quantization over the whole
image (after dropping near-white pixels), then nearest-neighbor mapping
onto VISTIQ's supported color palette (`ml/labels/clothing_categories.json`).
Its one real weakness: it only filters near-white backgrounds, so any
other background color (black, colored, patterned) competes directly with
the garment for "dominant color."

**Phase 2 (primary path — `ml/inference/segmentation.py` +
`ml/inference/color_advanced.py`):**
1. `segmentation.segment_foreground()` — OpenCV **GrabCut**, a classical
   iterative foreground/background separation algorithm (not a trained
   model, ships inside `opencv-python-headless`, no weights to download).
   Seeded with a centered rectangle (assumes a roughly centered garment,
   background nearer the edges — true for flat-lay/product photography).
   Images are downscaled to `SEGMENTATION_MAX_DIMENSION` (300px) before
   running GrabCut purely for speed — full-resolution GrabCut measured up
   to **74 seconds** on one real upload in this project, vs. 0.3-1.8s after
   downscaling. The resulting mask is validated (must cover between 5% and
   95% of the image) and upscaled back to the original size; a mask
   outside that range, a missing `cv2`, or any OpenCV error is treated as
   a failed segmentation.
2. `color_advanced.extract_color_profile()` — converts the (foreground-only,
   when segmentation succeeded) pixel sample to **HSV**, then runs
   **K-means** (`cv2.kmeans`, k=5) — an **unsupervised clustering
   algorithm**, explicitly not a predictive/trained model — to group pixels
   by color similarity. Clusters below 15% of the sample are treated as
   insignificant. The top cluster becomes `color` (primary); a second
   cluster is only reported as `secondary_color` if it's both significant
   and a genuinely different named color. `pattern` ("solid"/"patterned")
   and `brightness_level` are derived from the same cluster data at no
   extra cost. K-means's center-initialization RNG is reseeded to a fixed
   value before every call specifically so identical input always produces
   identical output.
3. **Fallback chain, never silent/empty:** if OpenCV is unavailable, the
   pixel sample is too small/degenerate, or K-means itself errors,
   `extract_color_profile()` falls back directly to the original Phase 1
   `extract_dominant_color()` — wrapped in the same structured result
   shape, with `reliability="low"` and `color_confidence=null`, so callers
   never need to special-case which path actually ran.

**`color_confidence`** reflects this: a real (non-ML) cluster-dominance
score (0-1) when the Phase 2 pipeline succeeds, `null` when it fell back to
the Phase 1 method — never a machine-learning confidence value either way.

**Known limitations of GrabCut here** (not hidden): it assumes a roughly
centered garment with background nearer the edges — a photo that doesn't
match that framing (off-center, cropped tight, worn by a person filling the
frame) will likely fail the foreground-fraction check and silently fall
back to the Phase 1 method rather than produce a wrong mask. It also
struggles when the background's color is close to the garment's own color.
Manual qualitative review on this project's real uploaded photos (flat-lay
style, roughly centered) showed GrabCut succeeding on essentially all of
them, with sensible primary/secondary colors and plausible solid/patterned
calls — but this has not been evaluated on a labeled dataset, and no
accuracy percentage is claimed for it.

## Image quality validation (Phase 2, not ML)

`ml/inference/image_quality.py` — runs before the classifier, so a useless
image doesn't waste a model forward pass. Three-way outcome:

- **Invalid (rejected, HTTP 400):** only when the image is below
  `MIN_HARD_DIMENSION` (32px either side) — genuinely no usable signal.
- **Low-quality (accepted, with a warning):** low resolution (below the
  model's native 224px input size), likely blurry (Laplacian variance below
  a threshold, measured after resizing to a fixed size so the threshold
  doesn't depend on the original photo's resolution), too dark, or
  overexposed (mean grayscale brightness outside a configured range).
- **Normal:** accepted, no warnings.

All thresholds are named constants in that module with their justification
in a comment next to them — not unexplained magic numbers — and are easy to
retune in one place.

## Workspace layout

```
ml/
├── README.md                         (this file)
├── notebooks/
│   └── vistiq_clothing_classifier_colab.ipynb   (train in Colab)
├── training/
│   ├── config.py                     (single source of truth: classes, hyperparameters, paths)
│   ├── dataset.py                    (loads clothing-dataset-small, remaps labels to VISTIQ categories)
│   ├── model.py                      (builds/saves/loads the MobileNetV3-Small classifier)
│   ├── train.py                      (two-phase training loop — run inside the notebook)
│   └── evaluate.py                   (test accuracy, per-class P/R/F1, confusion matrix, plots)
├── inference/
│   ├── predict.py                    (predict_clothing() — the contract FastAPI calls)
│   ├── color.py                      (Phase 1 deterministic color extraction — kept as the fallback)
│   ├── segmentation.py               (Phase 2: GrabCut foreground segmentation)
│   ├── color_advanced.py             (Phase 2: K-means color clustering, foreground-aware)
│   └── image_quality.py              (Phase 2: resolution/blur/exposure checks)
└── labels/
    └── clothing_categories.json      (dataset info, label mapping, color palette)

models/
├── README.md
└── vistiq_clothing_classifier.pt     (present — see models/README.md for how it was verified)
```

## Running the notebook

1. Upload `ml/notebooks/vistiq_clothing_classifier_colab.ipynb` to
   [Google Colab](https://colab.research.google.com) (or open directly from
   GitHub once this repo is pushed).
2. Runtime → Change runtime type → GPU (T4 is plenty for MobileNetV3-Small).
3. Run all cells top to bottom.
4. Download the exported `vistiq_clothing_classifier.pt` from the final cell.
5. Place it at `VistiQ/models/vistiq_clothing_classifier.pt`.
6. `ml/inference/predict.py` and the FastAPI `/analyze-clothing` endpoint
   will then work without any code changes — they already check for this
   exact path.

## Local inference (after a trained model is in place)

```bash
cd vistiq-backend
.venv\Scripts\python.exe -m ml.inference.predict path\to\photo.jpg
```

(Run from the project root so the `ml` package resolves — see
`app/services/clothing_analysis.py` for how the FastAPI backend locates it.)
