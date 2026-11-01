# VISTIQ trained models

## Expected file

```
models/vistiq_clothing_classifier.pt
```

A PyTorch `state_dict` for a MobileNetV3-Small fine-tuned on VISTIQ's 6
wardrobe categories (`Tops`, `Bottoms`, `Outerwear`, `Dresses`, `Footwear`,
`Accessories`). Produced by running
`ml/notebooks/vistiq_clothing_classifier_colab.ipynb` in Google Colab.

## Current status

**Not present.** This directory currently contains no trained model — only
this README. `ml/inference/predict.py` checks for this file at runtime and
raises a clear `ModelUnavailableError` if it's missing (see
`ml/inference/predict.is_model_available()`); the FastAPI `/analyze-clothing`
endpoint catches that and returns a clean service error rather than crashing
or fabricating a prediction.

## How to produce it

1. Open `ml/notebooks/vistiq_clothing_classifier_colab.ipynb` in Google Colab.
2. Enable a GPU runtime (Runtime → Change runtime type → GPU). The notebook
   also runs on CPU-only Colab, just much slower.
3. Run all cells top to bottom: dataset download, training (2-phase transfer
   learning), evaluation, and export.
4. The final cell saves `vistiq_clothing_classifier.pt` and offers a direct
   Colab download.
5. Place the downloaded file at `VistiQ/models/vistiq_clothing_classifier.pt`
   on your machine (same relative path, no code changes needed).

## Why it isn't committed yet

No GPU-trained model exists yet — training happens in Colab, not on this
Windows laptop (no NVIDIA GPU). Once a model is trained, evaluated, and
placed here, its file size will be reported here (MobileNetV3-Small
state_dicts are typically on the order of a few MB to ~10MB as float32,
well within a normal git repository's limits — no Git LFS is expected to be
necessary, but this will be confirmed once a real file exists).
