"""
Central configuration for the VISTIQ clothing classifier.

Every other module (dataset.py, model.py, train.py, evaluate.py,
inference/predict.py, and the Colab notebook) reads its constants from here
so training and inference can never silently drift out of sync — e.g. the
class order used at training time is exactly the class order the FastAPI
endpoint will interpret the model's output with.
"""

import json
from pathlib import Path

ML_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = ML_ROOT.parent

LABELS_PATH = ML_ROOT / "labels" / "clothing_categories.json"
MODELS_DIR = PROJECT_ROOT / "models"
MODEL_FILENAME = "vistiq_clothing_classifier.pt"
MODEL_PATH = MODELS_DIR / MODEL_FILENAME

with open(LABELS_PATH, "r", encoding="utf-8") as f:
    _LABELS = json.load(f)

# Single source of truth for class order. The index of each category here IS
# the index the model's output logits/softmax correspond to.
VISTIQ_CATEGORIES: list[str] = _LABELS["vistiq_categories"]
LABEL_MAPPING: dict[str, str] = _LABELS["label_mapping"]  # raw dataset label -> VISTIQ category
COLOR_PALETTE: dict[str, list[int]] = _LABELS["color_palette"]["buckets"]

# --- Model ------------------------------------------------------------------

MODEL_ARCHITECTURE = "mobilenet_v3_small"
NUM_CLASSES = len(VISTIQ_CATEGORIES)

# MobileNetV3's ImageNet-pretrained weights expect 224x224 RGB input,
# normalized with these exact ImageNet mean/std statistics.
IMAGE_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# --- Training -----------------------------------------------------------------

RANDOM_SEED = 42
BATCH_SIZE = 32

# Phase 1: backbone frozen, only the new classification head trains.
PHASE1_EPOCHS = 8
PHASE1_LR = 1e-3

# Phase 2: unfreeze the last few backbone blocks, fine-tune everything that's
# unfrozen at a much lower learning rate so pretrained features aren't wrecked.
PHASE2_EPOCHS = 6
PHASE2_LR = 1e-5
PHASE2_UNFREEZE_LAST_N_BLOCKS = 3

EARLY_STOPPING_PATIENCE = 3  # epochs without validation-accuracy improvement
CHECKPOINT_DIR = ML_ROOT / "training" / "checkpoints"

# --- Dataset ------------------------------------------------------------------

DATASET_REPO_URL = "https://github.com/alexeygrigorev/clothing-dataset-small.git"
DATASET_DIR_NAME = "clothing-dataset-small"
DATASET_SPLITS = ("train", "validation", "test")

# Low-confidence threshold used by inference — configurable, not a claim about
# model accuracy (see ml/inference/predict.py).
LOW_CONFIDENCE_THRESHOLD = 0.60
