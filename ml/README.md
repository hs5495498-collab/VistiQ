# VISTIQ Machine Learning Workspace (Stage 13)

Real, trained image understanding for VISTIQ's Add Clothing flow:

```
user uploads clothing photo
        ↓
MobileNetV3-Small classifier (trained via transfer learning)
        ↓
predicted VISTIQ category + confidence
        ↓
deterministic dominant-color extraction (image processing, not ML)
        ↓
predicted color
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

`ml/inference/color.py` — deterministic dominant-color extraction via
Pillow palette quantization, then nearest-neighbor mapping onto VISTIQ's
supported color palette (defined in `ml/labels/clothing_categories.json`).
No model, no training, no confidence score in the ML sense — this is why the
inference response's `color_confidence` field is always `null`. Explicitly
kept separate from the trained classifier so the API response never
conflates a real model's confidence with a deterministic heuristic's output.

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
│   └── color.py                      (deterministic dominant-color extraction)
└── labels/
    └── clothing_categories.json      (dataset info, label mapping, color palette)

models/
├── README.md
└── vistiq_clothing_classifier.pt     (NOT YET PRESENT — produced by the Colab notebook)
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
