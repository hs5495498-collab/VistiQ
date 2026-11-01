"""
MobileNetV3-Small transfer-learning classifier for VISTIQ clothing categories.

Why MobileNetV3-Small:
- Lightweight (~2.5M parameters, ~10MB as float32 weights) — fast to fine-tune
  in Colab and fast enough for CPU inference on a laptop with no GPU.
- Pretrained on ImageNet, so it already has useful general visual features
  (edges, textures, shapes) before we ever show it a clothing photo.
- Small enough to explain end-to-end in a viva: "pretrained feature
  extractor + a small classification head we trained ourselves."
"""

import torch
import torch.nn as nn
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

from ml.training.config import NUM_CLASSES


def build_model(num_classes: int = NUM_CLASSES, pretrained: bool = True) -> nn.Module:
    """Build a MobileNetV3-Small with its classifier head replaced for
    `num_classes` VISTIQ categories.

    pretrained=True  -> load ImageNet weights (used at the start of training).
    pretrained=False -> random init (used when loading OUR OWN trained
                         weights afterwards, e.g. at inference time, so we
                         don't waste time/bandwidth re-downloading ImageNet
                         weights we're about to overwrite anyway).
    """
    weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None
    model = mobilenet_v3_small(weights=weights)

    # torchvision's MobileNetV3-Small classifier is:
    #   Linear(576 -> 1024) -> Hardswish -> Dropout -> Linear(1024 -> 1000)
    # We keep the first two layers (they're a general-purpose feature
    # projection) and only replace the final layer so it outputs our 6
    # VISTIQ categories instead of 1000 ImageNet classes.
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)

    return model


def freeze_backbone(model: nn.Module) -> None:
    """Phase 1: freeze every layer except the classifier head."""
    for name, param in model.named_parameters():
        param.requires_grad = name.startswith("classifier")


def unfreeze_last_blocks(model: nn.Module, n_blocks: int) -> None:
    """Phase 2: additionally unfreeze the last `n_blocks` feature blocks so
    fine-tuning can adapt higher-level features to clothing photos, while
    early layers (generic edge/texture detectors) stay frozen."""
    feature_blocks = list(model.features.children())
    for block in feature_blocks[-n_blocks:]:
        for param in block.parameters():
            param.requires_grad = True


def count_trainable_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def save_model(model: nn.Module, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), path)


def load_model(path, num_classes: int = NUM_CLASSES) -> nn.Module:
    """Load OUR trained weights (not ImageNet weights) for inference.

    Accepts either a raw state_dict (what save_model() above writes) or a
    checkpoint dict wrapping the weights under "model_state_dict" alongside
    export metadata (categories/num_classes/image_size/architecture/
    test_accuracy) — the format the actual Colab training notebook exports.
    """
    model = build_model(num_classes=num_classes, pretrained=False)
    checkpoint = torch.load(path, map_location="cpu")
    state_dict = checkpoint["model_state_dict"] if "model_state_dict" in checkpoint else checkpoint
    model.load_state_dict(state_dict)
    model.eval()
    return model
