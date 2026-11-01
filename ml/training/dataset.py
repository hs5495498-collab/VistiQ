"""
Dataset loading for clothing-dataset-small, remapped from its 10 raw folder
labels onto the 6 VISTIQ categories defined in labels/clothing_categories.json.

The dataset ships its own train/validation/test folders (see ml/README.md for
how it was verified), so we use that split as-is rather than re-splitting —
it's the dataset author's own reproducible split, referenceable by anyone who
clones the same repo.
"""

from pathlib import Path

import torch
from torch.utils.data import DataLoader
from torchvision import transforms
from torchvision.datasets import ImageFolder

from ml.training.config import (
    BATCH_SIZE,
    IMAGE_SIZE,
    IMAGENET_MEAN,
    IMAGENET_STD,
    LABEL_MAPPING,
    VISTIQ_CATEGORIES,
)

VISTIQ_CATEGORY_TO_IDX = {name: i for i, name in enumerate(VISTIQ_CATEGORIES)}


def build_transforms(train: bool) -> transforms.Compose:
    """Preprocessing matches MobileNetV3's ImageNet training statistics.

    Augmentation is deliberately mild — clothing category/color/silhouette
    are the signal we want the model to learn, so we avoid heavy distortions
    (no aggressive cropping, no color jitter strong enough to change a
    garment's apparent color, no vertical flips which would make clothing
    look upside-down/unrealistic).
    """
    if train:
        return transforms.Compose(
            [
                transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.ColorJitter(brightness=0.15, contrast=0.15),
                transforms.RandomRotation(degrees=8),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ]
        )
    return transforms.Compose(
        [
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


def _remap_target_transform(raw_class_to_idx: dict[str, int]):
    """Build a function that converts an ImageFolder raw class index (one of
    the 10 dataset folders) into a VISTIQ category index (one of 6)."""
    raw_idx_to_vistiq_idx = {}
    for raw_label, raw_idx in raw_class_to_idx.items():
        if raw_label not in LABEL_MAPPING:
            raise ValueError(
                f"Dataset folder '{raw_label}' has no entry in "
                f"labels/clothing_categories.json label_mapping — "
                f"update the mapping before training."
            )
        vistiq_category = LABEL_MAPPING[raw_label]
        raw_idx_to_vistiq_idx[raw_idx] = VISTIQ_CATEGORY_TO_IDX[vistiq_category]

    def remap(raw_idx: int) -> int:
        return raw_idx_to_vistiq_idx[raw_idx]

    return remap


def load_split(dataset_root: Path, split: str, train: bool) -> ImageFolder:
    """Load one split ('train' / 'validation' / 'test') as an ImageFolder
    whose labels are already remapped to VISTIQ category indices."""
    split_dir = dataset_root / split
    if not split_dir.exists():
        raise FileNotFoundError(
            f"Expected dataset split at {split_dir} — did you clone "
            f"clothing-dataset-small into {dataset_root}?"
        )

    dataset = ImageFolder(root=str(split_dir), transform=build_transforms(train=train))
    dataset.target_transform = _remap_target_transform(dataset.class_to_idx)
    return dataset


def build_dataloaders(dataset_root: Path, batch_size: int = BATCH_SIZE):
    train_ds = load_split(dataset_root, "train", train=True)
    val_ds = load_split(dataset_root, "validation", train=False)
    test_ds = load_split(dataset_root, "test", train=False)

    generator = torch.Generator().manual_seed(42)
    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True, generator=generator, num_workers=0
    )
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    return train_loader, val_loader, test_loader, (train_ds, val_ds, test_ds)


def summarize_class_distribution(dataset: ImageFolder) -> dict[str, int]:
    """Real counts per VISTIQ category for a loaded split — used to print
    (never fabricate) the class distribution during dataset inspection."""
    remap = dataset.target_transform
    counts = {name: 0 for name in VISTIQ_CATEGORIES}
    for _, raw_idx in dataset.samples:
        vistiq_idx = remap(raw_idx)
        counts[VISTIQ_CATEGORIES[vistiq_idx]] += 1
    return counts
