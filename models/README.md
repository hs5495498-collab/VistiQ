# VISTIQ trained models

## File

```
models/vistiq_clothing_classifier.pt
```

A checkpoint for a MobileNetV3-Small fine-tuned on VISTIQ's 6 wardrobe
categories (`Tops`, `Bottoms`, `Outerwear`, `Dresses`, `Footwear`,
`Accessories`). Produced by running
`ml/notebooks/vistiq_clothing_classifier_colab.ipynb` in Google Colab.

Format: a `dict` wrapping the actual weights under `model_state_dict`,
alongside export metadata — `categories`, `num_classes`, `image_size`,
`architecture`, and `test_accuracy`. `ml/training/model.py`'s `load_model()`
unwraps `model_state_dict` before loading it into the plain MobileNetV3-Small
architecture (it also accepts a raw `state_dict` with no wrapper, for
flexibility, but the file actually produced by the Colab notebook is the
wrapped form).

## Current status

**Present, and verified in this repository.** File size: 6,234,981 bytes
(~5.9 MiB) — well within normal git limits, no Git LFS needed.

Verification performed (see `vistiq-backend/tests/test_model_smoke.py`,
which runs this check as part of the automated test suite, not just once
manually):

- The checkpoint's `model_state_dict` loads into a freshly-built
  MobileNetV3-Small with `strict=True` — exact key and shape match, no
  errors.
- A real CPU forward pass on a real uploaded photo produces a category
  prediction and confidence score through the actual FastAPI
  `/analyze-clothing` code path (`app/services/clothing_analysis.py` →
  `ml/inference/predict.py`).

**Not independently verified:** the embedded `test_accuracy: 0.9086`
metadata field. This repository does not contain the
`clothing-dataset-small` test split the number was computed against, nor any
saved confusion matrix / classification report, so that specific accuracy
figure is reported as training-time output, not reproduced here. See
`ml/README.md`'s Status section for how to reproduce it if needed.

## How to reproduce/retrain it

1. Open `ml/notebooks/vistiq_clothing_classifier_colab.ipynb` in Google Colab.
2. Enable a GPU runtime (Runtime → Change runtime type → GPU). The notebook
   also runs on CPU-only Colab, just much slower.
3. Run all cells top to bottom: dataset download, training (2-phase transfer
   learning), evaluation, and export.
4. The final cell saves `vistiq_clothing_classifier.pt` and offers a direct
   Colab download.
5. Place the downloaded file at `VistiQ/models/vistiq_clothing_classifier.pt`
   on your machine (same relative path, no code changes needed), replacing
   the existing one.
