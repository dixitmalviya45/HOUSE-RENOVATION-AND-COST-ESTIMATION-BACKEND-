"""OpenCV image quality validation and preprocessing."""

from __future__ import annotations

import io
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps


MIN_WIDTH = 640
MIN_HEIGHT = 480
BLUR_THRESHOLD = 100.0
MAX_LONG_SIDE = 1920
MAX_UPLOAD_BYTES = 500_000


def _decode_bgr(image_bytes: bytes) -> np.ndarray:
    """Decode image bytes to OpenCV BGR array."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image. Use JPG, PNG, or WEBP.")
    return image


def validate_image_quality(image_bytes: bytes) -> dict[str, Any]:
    """
    Check min resolution, blur (Laplacian variance), and brightness.

    Returns { is_valid, issues[], blur_score, resolution, brightness }.
    """
    issues: list[str] = []
    try:
        image = _decode_bgr(image_bytes)
    except ValueError as exc:
        return {
            "is_valid": False,
            "issues": [str(exc)],
            "blur_score": 0.0,
            "resolution": {"width": 0, "height": 0},
            "brightness": 0.0,
        }

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))

    if width < MIN_WIDTH or height < MIN_HEIGHT:
        issues.append(
            f"Resolution too low ({width}x{height}). Minimum is {MIN_WIDTH}x{MIN_HEIGHT}."
        )
    if blur_score < BLUR_THRESHOLD:
        issues.append(
            f"Image looks blurry (score {blur_score:.1f}). Use a sharper photo."
        )
    if brightness < 40:
        issues.append("Image is too dark. Retake with better lighting.")
    elif brightness > 220:
        issues.append("Image is too bright / overexposed.")

    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "blur_score": round(blur_score, 2),
        "resolution": {"width": width, "height": height},
        "brightness": round(brightness, 2),
    }


def preprocess_image(image_bytes: bytes) -> bytes:
    """
    Auto-orient via EXIF, resize to max 1920px longest side,
    normalize contrast, and compress to ~500KB JPEG for Cloudinary.
    """
    pil = Image.open(io.BytesIO(image_bytes))
    pil = ImageOps.exif_transpose(pil)
    if pil.mode not in ("RGB", "L"):
        pil = pil.convert("RGB")
    elif pil.mode == "L":
        pil = pil.convert("RGB")

    width, height = pil.size
    longest = max(width, height)
    if longest > MAX_LONG_SIDE:
        scale = MAX_LONG_SIDE / longest
        pil = pil.resize(
            (int(width * scale), int(height * scale)),
            Image.Resampling.LANCZOS,
        )

    # Mild contrast/brightness normalize via OpenCV CLAHE on L channel
    bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_ch = clahe.apply(l_ch)
    merged = cv2.merge([l_ch, a_ch, b_ch])
    bgr = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    out = Image.fromarray(rgb)

    quality = 85
    buffer = io.BytesIO()
    out.save(buffer, format="JPEG", quality=quality, optimize=True)
    while buffer.tell() > MAX_UPLOAD_BYTES and quality > 40:
        quality -= 10
        buffer = io.BytesIO()
        out.save(buffer, format="JPEG", quality=quality, optimize=True)

    return buffer.getvalue()
