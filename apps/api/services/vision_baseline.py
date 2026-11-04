"""A deterministic fabric defect baseline that works before any model is trained.

Why this exists: the project has no labelled fabric data yet, and a dashboard with an empty
inspection panel teaches nobody anything. This is a classical texture-anomaly detector — no
training, no weights, no randomness — so the whole path (upload → inspect → stored defect boxes)
is exercisable today, and every number it produces can be reproduced byte for byte.

What it is not: it does not know what a hole is. It finds regions whose local brightness or local
texture deviates from the rest of the same image. Its labels (`dark_region`, `bright_region`,
`texture_irregularity`) describe the appearance, not the defect class in the SRS taxonomy. A
trained YOLO/U-Net replaces this module behind the same interface; the roadmap and
`ai-services/vision/README.md` describe that swap.

Why no scipy: the API image stays small, and a 40-line integral-image filter is dependency-free.
numpy and Pillow are already required for image handling.

Determinism: fixed constants, no RNG, no time-dependent behaviour, no dependence on image
metadata. Same bytes in, same boxes out — which is what makes it usable as a test fixture.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageOps

# Analysis resolution. Larger images are downscaled, then boxes are mapped back, so inference cost
# is bounded regardless of what a camera produces.
MAX_ANALYSIS_SIDE = 1024

LOCAL_WINDOW = 9

# Robust z-score threshold. 3.5 sigma on a MAD scale is deliberately conservative: this baseline
# should miss a subtle defect rather than fill the queue with noise it cannot explain.
Z_THRESHOLD = 3.5

MIN_AREA_FRACTION = 0.0002  # ignore specks: 0.02% of the frame
MAX_AREA_FRACTION = 0.25  # ignore "defects" covering a quarter of the image: that is lighting

FAIL_CONFIDENCE = 0.60

DARKNESS_DELTA = 0.06  # mean brightness difference that distinguishes dark from bright


@dataclass(frozen=True)
class Defect:
    defect_class: str
    confidence: float
    x: int
    y: int
    w: int
    h: int
    severity: str
    area_fraction: float

    def as_box(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass(frozen=True)
class DetectionResult:
    width: int
    height: int
    status: str
    defects: list[Defect] = field(default_factory=list)
    duration_ms: int = 0
    detector: str = "texture-anomaly-baseline/1"

    @property
    def is_clean(self) -> bool:
        return not self.defects


def _box_mean(array: np.ndarray, window: int) -> np.ndarray:
    """Mean over a window×window box, normalising by how many real pixels each box saw.

    Zero-padding without the count normalisation is a classic mistake: it manufactures a dark ring
    at the border, and the detector then reports a defect on the edge of every image.
    """
    radius = window // 2
    padded = np.pad(array, radius, mode="constant", constant_values=0.0)
    ones = np.pad(np.ones_like(array), radius, mode="constant", constant_values=0.0)

    def _window_sum(a: np.ndarray) -> np.ndarray:
        integral = a.cumsum(0).cumsum(1)
        integral = np.pad(integral, ((1, 0), (1, 0)))
        return (
            integral[window:, window:]
            - integral[:-window, window:]
            - integral[window:, :-window]
            + integral[:-window, :-window]
        )

    counts = _window_sum(ones)
    return _window_sum(padded) / np.maximum(counts, 1.0)


def _local_std(array: np.ndarray, window: int) -> np.ndarray:
    mean = _box_mean(array, window)
    mean_of_squares = _box_mean(array * array, window)
    return np.sqrt(np.maximum(mean_of_squares - mean * mean, 0.0))


def _block_mean(array: np.ndarray, factor: int) -> np.ndarray:
    """Crop to whole blocks, then average each one. The crop is why analysis size is bounded."""
    height, width = array.shape
    height -= height % factor
    width -= width % factor
    cropped = array[:height, :width]
    return cropped.reshape(height // factor, factor, width // factor, factor).mean(axis=(1, 3))


def _block_median(array: np.ndarray, kernel: int) -> np.ndarray:
    """Median filter over a small array (one entry per block), edge-padded.

    Median, not mean: a defect must not move the estimate of normal. A mean background is dragged
    towards the stain and leaves a halo around it, which is exactly how a 20-pixel hole becomes an
    80-pixel box.
    """
    radius = kernel // 2
    padded = np.pad(array, radius, mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, (kernel, kernel))
    return np.median(windows.reshape(windows.shape[0], windows.shape[1], -1), axis=2)


def _background(array: np.ndarray, factor: int = 8, kernel: int = 5) -> np.ndarray:
    """Robust estimate of "normal fabric" at pixel resolution, by pooled block median."""
    height, width = array.shape
    small = _block_median(_block_mean(array, factor), kernel)
    upscaled = np.repeat(np.repeat(small, factor, axis=0), factor, axis=1)
    # The block crop can shorten an axis by up to factor-1 pixels; edge-pad back to exact size.
    return np.pad(
        upscaled, ((0, height - upscaled.shape[0]), (0, width - upscaled.shape[1])), mode="edge"
    )


# Floor on the MAD scale, in image-normalised units (1/255 ≈ the smallest visible step). Without
# it, plain fabric has a MAD of zero, and every deviation becomes "infinitely many sigma" - which
# either detects nothing or detects everything depending on the guard.
MIN_SCALE = 0.004


def _robust_z(values: np.ndarray) -> np.ndarray:
    """Signed z-score on a median/MAD scale.

    A plain mean/std would be dominated by the defect we are looking for: one large stain inflates
    the standard deviation and hides itself within its own statistics.
    """
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    scale = max(1.4826 * mad, MIN_SCALE)
    return (values - median) / scale


def _components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    """4-connected components. BFS in Python is fine because the mask is sparse by construction."""
    seen = np.zeros_like(mask, dtype=bool)
    height, width = mask.shape
    found: list[list[tuple[int, int]]] = []

    ys, xs = np.nonzero(mask)
    for start_y, start_x in zip(ys.tolist(), xs.tolist(), strict=True):
        if seen[start_y, start_x]:
            continue
        seen[start_y, start_x] = True
        stack = [(start_y, start_x)]
        pixels: list[tuple[int, int]] = []
        while stack:
            y, x = stack.pop()
            pixels.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        found.append(pixels)
    return found


def _shift_or(mask: np.ndarray, fill_value: bool) -> np.ndarray:
    """3×3 neighbourhood reduce with padding, not roll().

    np.roll wraps pixels from the opposite edge. On a fabric image that fabricates a defect every
    time the edge happens to be darker than the opposite edge.
    """
    padded = np.pad(mask, 1, mode="constant", constant_values=fill_value)
    out = np.zeros_like(mask)
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            out |= padded[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
    return out


def _open_mask(mask: np.ndarray) -> np.ndarray:
    """Erode then dilate, 3×3, to drop single-pixel noise without smearing real regions."""
    padded = np.pad(mask, 1, mode="constant", constant_values=False)
    eroded = mask.copy()
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            eroded &= padded[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
    return _shift_or(eroded, False)


def _confidence(z_score: float) -> float:
    """Map a z-score onto (0, 1) with a logistic curve centred on the threshold.

    This is a *heuristic score*, not a calibrated probability. It is stored in a column called
    confidence_score because that is the SRS contract; `docs/inspection-baseline.md` states plainly
    that calibration arrives with a trained model.
    """
    value = 1.0 / (1.0 + np.exp(-(z_score - Z_THRESHOLD) / 1.5))
    return round(float(min(max(value, 0.05), 0.99)), 4)


def _severity(area_fraction: float) -> str:
    if area_fraction < 0.005:
        return "minor"
    if area_fraction < 0.03:
        return "major"
    return "critical"


def _classify(mean_inside: float, mean_outside: float) -> str:
    delta = mean_inside - mean_outside
    if delta <= -DARKNESS_DELTA:
        return "dark_region"
    if delta >= DARKNESS_DELTA:
        return "bright_region"
    return "texture_irregularity"


def detect(image_bytes: bytes) -> DetectionResult:
    """Inspect one fabric image. Raises ValueError on input that cannot be decoded as an image."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except Exception as exc:  # PIL raises a variety of types for malformed input
        raise ValueError("Image could not be decoded.") from exc

    original_width, original_height = image.size
    if original_width < 16 or original_height < 16:
        raise ValueError("Image is too small to inspect.")

    # EXIF orientation and greyscale: a sideways or 4-band image would otherwise produce spurious
    # edges that look exactly like defects.
    image = ImageOps.exif_transpose(image).convert("L")

    scale = min(1.0, MAX_ANALYSIS_SIDE / max(image.size))
    if scale < 1.0:
        image = image.resize(
            (max(16, int(image.width * scale)), max(16, int(image.height * scale))),
            Image.BILINEAR,
        )

    grey = np.asarray(image, dtype=np.float64) / 255.0
    height, width = grey.shape

    # Two features, both local: a brightness residual (high-pass against a large background window)
    # and a texture deviation. A slow illumination gradient cancels in the difference of means,
    # which is why an evenly lit photo of plain fabric scores zero.
    background_mean = _background(grey)
    brightness = grey - background_mean

    local_texture = _local_std(grey, LOCAL_WINDOW)
    texture = local_texture - _background(local_texture)

    z_brightness = np.abs(_robust_z(brightness))
    z_texture = _robust_z(texture)  # one-sided: a smoother patch is a hole, a rougher one a tear

    combined = np.maximum(z_brightness, np.maximum(z_texture, 0.0))
    mask = combined > Z_THRESHOLD
    if not mask.any():
        return DetectionResult(width=original_width, height=original_height, status="pass")

    mask = _open_mask(mask)

    min_area = MIN_AREA_FRACTION * mask.size
    max_area = MAX_AREA_FRACTION * mask.size

    defects: list[Defect] = []
    for pixels in _components(mask):
        area = len(pixels)
        if area < min_area or area > max_area:
            continue

        ys = [p[0] for p in pixels]
        xs = [p[1] for p in pixels]
        y0, y1 = min(ys), max(ys)
        x0, x1 = min(xs), max(xs)

        inside = grey[y0 : y1 + 1, x0 : x1 + 1]
        # Immediate surroundings, so a stain is compared with the fabric next to it rather than with
        # the whole frame (which may be half shadow).
        pad = LOCAL_WINDOW
        ring = grey[
            max(0, y0 - pad) : min(height, y1 + pad + 1),
            max(0, x0 - pad) : min(width, x1 + pad + 1),
        ]
        outside_mean = float(ring.mean()) if ring.size else float(background_mean.mean())

        peak = float(combined[ys, xs].max())
        area_fraction = area / mask.size

        # Back to original pixels so stored boxes line up with the uploaded image.
        defects.append(
            Defect(
                defect_class=_classify(float(inside.mean()), outside_mean),
                confidence=_confidence(peak),
                x=int(round(x0 / scale)),
                y=int(round(y0 / scale)),
                w=int(round((x1 - x0 + 1) / scale)),
                h=int(round((y1 - y0 + 1) / scale)),
                severity=_severity(area_fraction),
                area_fraction=round(area_fraction, 6),
            )
        )

    defects.sort(key=lambda d: (-d.confidence, -d.area_fraction))
    if not defects:
        status = "pass"
    elif any(d.confidence >= FAIL_CONFIDENCE for d in defects):
        status = "fail"
    else:
        # Something is there, but not confidently enough to stop a roll. A human decides.
        status = "uncertain"

    return DetectionResult(
        width=original_width,
        height=original_height,
        status=status,
        defects=defects,
    )


def content_hash(image_bytes: bytes) -> str:
    """SHA-256 of the bytes. Used for dedupe and as the storage key — never for identity of a defect."""
    return hashlib.sha256(image_bytes).hexdigest()
