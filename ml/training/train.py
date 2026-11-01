"""
Two-phase transfer-learning training loop for the VISTIQ clothing classifier.

Meant to be run inside the Colab notebook (ml/notebooks/vistiq_clothing_classifier_colab.ipynb),
which has GPU access and the dataset downloaded. This module is also
importable/runnable standalone (`python -m ml.training.train`) if a GPU
machine with the dataset already in place is available — but per the VISTIQ
hardware constraint, the Windows dev laptop has no NVIDIA GPU and should not
be used to run this.

Phase 1: freeze the pretrained backbone, train only the new classifier head.
Phase 2: unfreeze the last few backbone blocks, fine-tune at a low LR.

Both phases use early stopping on validation accuracy and checkpoint the best
weights seen so far, so a run that plateaus or starts overfitting doesn't
overwrite a better earlier checkpoint.
"""

import copy
import time

import torch
import torch.nn as nn

from ml.training.config import (
    CHECKPOINT_DIR,
    EARLY_STOPPING_PATIENCE,
    MODEL_PATH,
    PHASE1_EPOCHS,
    PHASE1_LR,
    PHASE2_EPOCHS,
    PHASE2_LR,
    PHASE2_UNFREEZE_LAST_N_BLOCKS,
    RANDOM_SEED,
)
from ml.training.model import build_model, freeze_backbone, save_model, unfreeze_last_blocks


def set_seed(seed: int = RANDOM_SEED) -> None:
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def run_epoch(model, loader, criterion, optimizer, device, train: bool) -> tuple[float, float]:
    model.train(mode=train)
    total_loss, correct, total = 0.0, 0, 0

    context = torch.enable_grad() if train else torch.no_grad()
    with context:
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)

            if train:
                optimizer.zero_grad()

            outputs = model(images)
            loss = criterion(outputs, labels)

            if train:
                loss.backward()
                optimizer.step()

            total_loss += loss.item() * images.size(0)
            correct += (outputs.argmax(dim=1) == labels).sum().item()
            total += images.size(0)

    return total_loss / total, correct / total


def train_phase(
    model, train_loader, val_loader, device, epochs: int, lr: float, phase_name: str,
    history: dict, best_state: dict,
):
    criterion = nn.CrossEntropyLoss()
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.Adam(trainable_params, lr=lr)

    epochs_without_improvement = 0

    for epoch in range(1, epochs + 1):
        start = time.time()
        train_loss, train_acc = run_epoch(model, train_loader, criterion, optimizer, device, train=True)
        val_loss, val_acc = run_epoch(model, val_loader, criterion, optimizer, device, train=False)
        elapsed = time.time() - start

        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)
        history["phase"].append(phase_name)

        print(
            f"[{phase_name}] epoch {epoch}/{epochs} "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f} "
            f"({elapsed:.1f}s)"
        )

        if val_acc > best_state["val_acc"]:
            best_state["val_acc"] = val_acc
            best_state["weights"] = copy.deepcopy(model.state_dict())
            epochs_without_improvement = 0

            CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), CHECKPOINT_DIR / f"best_{phase_name}.pt")
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= EARLY_STOPPING_PATIENCE:
                print(f"[{phase_name}] no improvement for {EARLY_STOPPING_PATIENCE} epochs — stopping early.")
                break

    return history, best_state


def train_model(train_loader, val_loader, num_classes: int, device: torch.device):
    """Runs both training phases and returns (model, history). The caller
    (notebook) is responsible for calling evaluate.py on the held-out test
    set afterwards and for exporting the final model with save_model()."""
    set_seed()

    model = build_model(num_classes=num_classes, pretrained=True)
    model.to(device)

    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": [], "phase": []}
    best_state = {"val_acc": 0.0, "weights": None}

    # Phase 1 — frozen backbone, train the head only.
    freeze_backbone(model)
    history, best_state = train_phase(
        model, train_loader, val_loader, device,
        epochs=PHASE1_EPOCHS, lr=PHASE1_LR, phase_name="phase1_head",
        history=history, best_state=best_state,
    )

    # Phase 2 — unfreeze the last few blocks, fine-tune at a low LR.
    unfreeze_last_blocks(model, PHASE2_UNFREEZE_LAST_N_BLOCKS)
    history, best_state = train_phase(
        model, train_loader, val_loader, device,
        epochs=PHASE2_EPOCHS, lr=PHASE2_LR, phase_name="phase2_finetune",
        history=history, best_state=best_state,
    )

    if best_state["weights"] is not None:
        model.load_state_dict(best_state["weights"])

    return model, history, best_state["val_acc"]


if __name__ == "__main__":
    raise SystemExit(
        "Run this training loop inside the Colab notebook "
        "(ml/notebooks/vistiq_clothing_classifier_colab.ipynb), which has GPU "
        "access and downloads the dataset. The Windows dev laptop has no "
        "NVIDIA GPU and should not be used for training."
    )
