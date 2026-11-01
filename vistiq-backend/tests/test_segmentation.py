"""Tests for ml/inference/segmentation.py (Phase 2: GrabCut foreground
segmentation). Uses small synthetic images for speed — real-photo
segmentation quality is additionally exercised, unmocked, by
tests/test_model_smoke.py and by the manual qualitative checks described
in the Phase 2 completion report."""

from PIL import Image

from ml.inference import segmentation


def _two_tone_image(size=(120, 120), fg_color=(20, 20, 160), bg_color=(250, 250, 250), margin=25) -> Image.Image:
    """A bright, uniform 'background' with a distinctly different,
    centered 'garment' block — the shape GrabCut's centered-rect seed is
    designed for."""
    image = Image.new("RGB", size, color=bg_color)
    for y in range(margin, size[1] - margin):
        for x in range(margin, size[0] - margin):
            image.putpixel((x, y), fg_color)
    return image


def test_successful_segmentation_on_clear_foreground_background_image():
    image = _two_tone_image()
    result = segmentation.segment_foreground(image)

    assert result.success is True
    assert result.method == "grabcut"
    assert result.mask is not None
    assert result.mask.shape == (image.height, image.width)
    assert segmentation.MIN_FOREGROUND_FRACTION <= result.foreground_fraction <= segmentation.MAX_FOREGROUND_FRACTION
    assert result.detail  # never empty


def test_segmentation_mask_is_same_size_as_original_image_even_when_downscaled():
    """A larger-than-SEGMENTATION_MAX_DIMENSION image gets downscaled
    internally for speed — the returned mask must still match the
    ORIGINAL image's dimensions, not the internal working size."""
    size = (segmentation.SEGMENTATION_MAX_DIMENSION + 150, segmentation.SEGMENTATION_MAX_DIMENSION + 300)
    image = _two_tone_image(size=size, margin=60)

    result = segmentation.segment_foreground(image)

    assert result.mask.shape == (size[1], size[0])


def test_segmentation_never_returns_a_mask_without_success():
    """Contract check: mask is None whenever success is False — callers
    must never receive a mask they haven't been told is trustworthy."""
    # A uniform solid image has no foreground/background contrast at all —
    # likely to either fail outright or produce a degenerate (whole-image
    # or near-empty) mask that the fraction sanity check rejects.
    image = Image.new("RGB", (64, 64), color=(128, 128, 128))
    result = segmentation.segment_foreground(image)

    if not result.success:
        assert result.mask is None
    assert result.detail


def test_segmentation_fails_gracefully_on_tiny_image():
    image = Image.new("RGB", (5, 5), color=(10, 10, 10))
    result = segmentation.segment_foreground(image)

    assert result.success is False
    assert result.mask is None
    assert result.method == "failed"
    assert "small" in result.detail.lower()


def test_segmentation_result_detail_is_always_populated():
    """Never return an empty/invalid result silently — `detail` must be a
    non-empty, human-readable string on every outcome."""
    for image in (
        _two_tone_image(),
        Image.new("RGB", (5, 5), color=(0, 0, 0)),
        Image.new("RGB", (64, 64), color=(200, 200, 200)),
    ):
        result = segmentation.segment_foreground(image)
        assert isinstance(result.detail, str) and len(result.detail) > 0
