"""
Evaluation helpers: held-out test accuracy, per-class precision/recall/F1,
confusion matrix, and accuracy/loss curve plotting.

Everything here reports REAL numbers computed from a REAL model and a REAL
held-out test set — nothing here should ever be called with fabricated
inputs to produce a report. If the model or test set isn't available yet,
these functions simply aren't called (see ml/README.md's training status).
"""

import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import classification_report, confusion_matrix

from ml.training.config import VISTIQ_CATEGORIES


@torch.no_grad()
def collect_predictions(model, loader, device):
    model.eval()
    all_preds, all_labels = [], []
    for images, labels in loader:
        images = images.to(device)
        outputs = model(images)
        preds = outputs.argmax(dim=1).cpu().numpy()
        all_preds.extend(preds.tolist())
        all_labels.extend(labels.numpy().tolist())
    return np.array(all_labels), np.array(all_preds)


def evaluate_model(model, test_loader, device) -> dict:
    labels, preds = collect_predictions(model, test_loader, device)
    accuracy = float((labels == preds).mean())

    report = classification_report(
        labels, preds, target_names=VISTIQ_CATEGORIES, output_dict=True, zero_division=0
    )
    cm = confusion_matrix(labels, preds, labels=list(range(len(VISTIQ_CATEGORIES))))

    return {
        "test_accuracy": accuracy,
        "num_test_samples": int(len(labels)),
        "classification_report": report,
        "confusion_matrix": cm,
    }


def print_evaluation_summary(results: dict) -> None:
    print(f"Test accuracy: {results['test_accuracy']:.4f} "
          f"({results['num_test_samples']} test images)")
    print()
    report = results["classification_report"]
    print(f"{'category':<14} {'precision':>10} {'recall':>10} {'f1':>10} {'support':>10}")
    for name in VISTIQ_CATEGORIES:
        row = report[name]
        print(f"{name:<14} {row['precision']:>10.3f} {row['recall']:>10.3f} "
              f"{row['f1-score']:>10.3f} {row['support']:>10.0f}")


def plot_confusion_matrix(cm, ax=None):
    ax = ax or plt.gca()
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(VISTIQ_CATEGORIES)))
    ax.set_yticks(range(len(VISTIQ_CATEGORIES)))
    ax.set_xticklabels(VISTIQ_CATEGORIES, rotation=45, ha="right")
    ax.set_yticklabels(VISTIQ_CATEGORIES)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("VISTIQ clothing classifier — confusion matrix (test set)")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                     color="white" if cm[i, j] > cm.max() / 2 else "black")
    plt.colorbar(im, ax=ax)
    return ax


def plot_training_curves(history: dict):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    ax1.plot(history["train_loss"], label="train")
    ax1.plot(history["val_loss"], label="validation")
    ax1.set_title("Loss")
    ax1.set_xlabel("epoch")
    ax1.legend()

    ax2.plot(history["train_acc"], label="train")
    ax2.plot(history["val_acc"], label="validation")
    ax2.set_title("Accuracy")
    ax2.set_xlabel("epoch")
    ax2.legend()

    fig.tight_layout()
    return fig
