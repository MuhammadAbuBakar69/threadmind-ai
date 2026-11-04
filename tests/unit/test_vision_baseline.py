"""The vision baseline, tested on synthetic fabric it cannot overfit to.

Every image here is generated in the test: a weave-like pattern plus Gaussian noise, then a known
defect painted at a known coordinate. That makes the expectation exact — a box either overlaps the
painted region or the detector is wrong — which a fixture photo taken from a dataset would not.

The tests that matter most are the negative ones. A detector that flags a defect on every image
passes any "did it find the hole" test; it fails `test_plain_fabric_is_clean` and
`test_a_smooth_illumination_gradient_is_not_a_defect`.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image
from services.vision_baseline import content_hash, detect

SIZE = 256


def _png(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(np.clip(array, 0, 255).astype("uint8")).save(buffer, format="PNG")
    return buffer.getvalue()


def fabric(seed: int = 7, size: int = SIZE) -> np.ndarray:
    """Mid-grey fabric with a fine weave and sensor noise. Deterministic for a given seed."""
    rng = np.random.default_rng(seed)
    weave = ((np.indices((size, size)).sum(0) % 4) - 1.5) * 3.0
    return np.full((size, size), 128.0) + weave + rng.normal(0.0, 2.0, (size, size))


def iou(box: tuple[int, int, int, int], truth: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = box
    bx, by, bw, bh = truth
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    intersection = (x1 - x0) * (y1 - y0)
    union = aw * ah + bw * bh - intersection
    return intersection / union


def test_plain_fabric_is_clean():
    result = detect(_png(fabric()))
    assert result.status == "pass"
    assert result.defects == []


def test_a_smooth_illumination_gradient_is_not_a_defect():
    """Factory lighting is uneven. A detector that reports the dark side of the frame as a defect is
    useless, and this is the cheap way to catch a background estimate that is not illumination
    invariant."""
    rng = np.random.default_rng(11)
    gradient = np.tile(np.linspace(40, 220, SIZE), (SIZE, 1)) + rng.normal(0.0, 2.0, (SIZE, SIZE))

    result = detect(_png(gradient))
    assert result.status == "pass"
    assert result.defects == []


def test_a_hole_is_detected_where_it_actually_is():
    image = fabric()
    truth = (150, 100, 20, 20)  # x, y, w, h
    image[100:120, 150:170] = 25.0  # dark patch: a hole against a light weave

    result = detect(_png(image))

    assert result.status == "fail"
    worst = result.defects[0]
    assert worst.defect_class == "dark_region"
    assert iou((worst.x, worst.y, worst.w, worst.h), truth) > 0.3
    assert worst.confidence >= 0.6


def test_a_localised_box_not_a_halo():
    """Regression guard. An earlier version estimated "normal" with a large box mean, which the
    defect dragged towards itself, and a 20-pixel hole came back as an 80-pixel box."""
    image = fabric()
    image[100:120, 150:170] = 25.0

    worst = detect(_png(image)).defects[0]
    assert worst.w < 3 * 20 and worst.h < 3 * 20


def test_a_bright_stain_is_detected_and_classified_as_bright():
    image = fabric()
    image[60:90, 40:90] = np.clip(image[60:90, 40:90] + 60.0, 0, 255)

    result = detect(_png(image))

    assert result.status == "fail"
    stain = result.defects[0]
    assert stain.defect_class == "bright_region"
    assert iou((stain.x, stain.y, stain.w, stain.h), (40, 60, 50, 30)) > 0.2


def test_detection_is_deterministic():
    """Same bytes, same boxes. Without this the detector cannot be a test fixture or a baseline."""
    image = fabric()
    image[100:120, 150:170] = 25.0
    payload = _png(image)

    first, second = detect(payload), detect(payload)

    assert [(d.defect_class, d.x, d.y, d.w, d.h, d.confidence) for d in first.defects] == [
        (d.defect_class, d.x, d.y, d.w, d.h, d.confidence) for d in second.defects
    ]


def test_boxes_are_reported_in_original_pixel_coordinates():
    """A 2000-pixel image is downscaled for analysis; the stored box must still point at the defect
    in the image the user uploaded, or every overlay in the dashboard is wrong."""
    big = fabric(seed=3, size=2000)
    big[1400:1480, 1500:1580] = 30.0

    result = detect(_png(big))

    assert result.width == 2000 and result.height == 2000
    worst = result.defects[0]
    assert iou((worst.x, worst.y, worst.w, worst.h), (1500, 1400, 80, 80)) > 0.2


def test_an_undecodable_payload_is_rejected():
    with pytest.raises(ValueError):
        detect(b"this is not an image")


def test_a_too_small_image_is_rejected():
    with pytest.raises(ValueError):
        detect(_png(np.full((8, 8), 128.0)))


def test_content_hash_is_stable_and_content_addressed():
    payload = _png(fabric())
    assert content_hash(payload) == content_hash(_png(fabric()))
    assert content_hash(payload) != content_hash(payload + b"\x00")


def test_a_uniform_image_does_not_invent_defects():
    """No texture at all: the MAD scale collapses to zero, and the floor must prevent a divide that
    turns floating-point dust into a defect."""
    result = detect(_png(np.full((SIZE, SIZE), 128.0)))
    assert result.defects == []
