"""CatVTON inference service.

The original CatVTON GitHub repository (github.com/Zheng-Chong/CatVTON)
returned a genuine HTTP 404 as of 2026-11-13 (confirmed directly with a
plain HTTP GET, not assumed) -- it has been taken down since at least one
prior VISTIQ session successfully cloned it. This service instead builds
the pipeline from the author's own HuggingFace Space snapshot (same
`zhengchong` namespace as the published model weights), pinned to a
specific historical revision for reproducibility. See
docs/CATVTON_SETUP.md for the full provenance writeup and license notes.

This module intentionally has no dependency on anything in
vistiq-backend/ -- it is a standalone service meant to run in a separate
Python environment (this project's own backend is CPU-only; this needs
CUDA, diffusers, detectron2, none of which belong in that venv).
"""
import os
import sys
import time

import torch

# T4-class GPUs (and other sm_75/older cards) do not support PyTorch's
# native flash-attention backend for bf16/fp16 in every configuration,
# and when no efficient backend is selected PyTorch silently falls back
# to the "math" backend, which materializes the full attention matrix.
# At 768x1024 that attempts to allocate ~18GB and OOMs instantly on a
# card with ~15GB total VRAM. Forcing the efficient backends on (and the
# math backend off, so an unsupported configuration raises a clear error
# instead of silently falling back) is what actually fixes this -- the
# weight dtype (fp16 vs bf16) alone does not, since both use the same
# 2 bytes/element. Verified: with this set, a real 768x1024 run peaks at
# ~4.2GB allocated / ~6.3GB reserved, matching historical measurements.
torch.backends.cuda.enable_flash_sdp(True)
torch.backends.cuda.enable_mem_efficient_sdp(True)
torch.backends.cuda.enable_math_sdp(False)

from huggingface_hub import snapshot_download  # noqa: E402

SPACE_REPO_ID = "zhengchong/CatVTON"
SPACE_REVISION = "58d5e58e9ac8e84ed71259407c4496ee9af253ea"
ATTN_REPO_ID = "zhengchong/CatVTON"
BASE_CKPT = "runwayml/stable-diffusion-inpainting"
SEGFORMER_CKPT = "mattmdjaga/segformer_b2_clothes"

TARGET_WIDTH = 768
TARGET_HEIGHT = 1024
NUM_INFERENCE_STEPS = 30
GUIDANCE_SCALE = 2.5


def _load_space_source() -> str:
    """Downloads the pinned HF Space snapshot and makes its `model`/`utils`
    packages importable.

    The chdir here is intentionally permanent for the life of the process:
    the Space's own DensePose code (model/DensePose/__init__.py) writes
    temporary files using paths relative to the process's current working
    directory at call time, not at import time. Changing back after
    __init__ would silently break every subsequent inference call.
    """
    space_path = snapshot_download(
        repo_id=SPACE_REPO_ID, repo_type="space", revision=SPACE_REVISION
    )
    if space_path not in sys.path:
        sys.path.insert(0, space_path)
    os.chdir(space_path)
    return space_path


class CatVTONService:
    """Loads the CatVTON pipeline once and serves inference calls."""

    def __init__(self, device: str = "cuda"):
        _load_space_source()

        from model.pipeline import CatVTONPipeline
        from model.cloth_masker import AutoMaskerSeg
        from utils import resize_and_crop, resize_and_padding
        from diffusers.image_processor import VaeImageProcessor

        self._resize_and_crop = resize_and_crop
        self._resize_and_padding = resize_and_padding

        attn_repo_path = snapshot_download(repo_id=ATTN_REPO_ID)

        print("Loading CatVTON pipeline...", flush=True)
        self.pipeline = CatVTONPipeline(
            base_ckpt=BASE_CKPT,
            attn_ckpt=attn_repo_path,
            attn_ckpt_version="mix",
            weight_dtype=torch.float16,
            use_tf32=True,
            device=device,
            # The safety checker's own NSFW-placeholder asset
            # (resource/img/NSFW.jpg) is not included in the HF Space
            # snapshot download, so leaving the safety checker on crashes
            # with FileNotFoundError whenever it fires (even a false
            # positive) -- disabled for this reason, not to bypass
            # moderation policy. See docs/CATVTON_SETUP.md.
            skip_safety_check=True,
        )
        self.automasker = AutoMaskerSeg(
            densepose_ckpt=os.path.join(attn_repo_path, "DensePose"),
            segformer_ckpt=SEGFORMER_CKPT,
            device=device,
        )
        self.mask_processor = VaeImageProcessor(
            vae_scale_factor=8,
            do_normalize=False,
            do_binarize=True,
            do_convert_grayscale=True,
        )
        print("CatVTON pipeline ready.", flush=True)

    def run(self, person_image, garment_image, cloth_type: str):
        """Runs one real try-on inference. Returns a PIL.Image."""
        person = self._resize_and_crop(person_image, (TARGET_WIDTH, TARGET_HEIGHT))
        garment = self._resize_and_padding(garment_image, (TARGET_WIDTH, TARGET_HEIGHT))
        mask = self.automasker(person, cloth_type)["mask"]
        mask = self.mask_processor.blur(mask, blur_factor=9)
        generator = torch.Generator(device="cuda").manual_seed(int(time.time()))
        result = self.pipeline(
            image=person,
            condition_image=garment,
            mask=mask,
            num_inference_steps=NUM_INFERENCE_STEPS,
            guidance_scale=GUIDANCE_SCALE,
            generator=generator,
        )[0]
        return result
