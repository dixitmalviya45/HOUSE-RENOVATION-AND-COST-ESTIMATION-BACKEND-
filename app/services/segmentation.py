"""Roboflow segmentation with usage tracking and OpenCV fallback."""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import Any

import cv2
import httpx
import numpy as np

from app.config import get_settings
from app.models.api_usage import ApiUsage
from app.models.project import Segment
from app.utils.helpers import year_month_key


REGION_TYPES = {
    "wall",
    "window",
    "balcony",
    "pillar",
    "door",
    "railing",
    "roof_edge",
    "parapet",
    "gate",
}


def _normalize_region_type(label: str) -> str:
    """Map model labels to our region_type enum."""
    raw = (label or "wall").lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "walls": "wall",
        "windows": "window",
        "window": "window",
        "doors": "door",
        "door": "door",
        "pillars": "pillar",
        "railings": "railing",
        "roof": "roof_edge",
        "roofs": "roof_edge",
        "parapets": "parapet",
        "gates": "gate",
        "balconies": "balcony",
        "building": "wall",
        "facade": "wall",
        "house": "wall",
    }
    mapped = aliases.get(raw, raw)
    return mapped if mapped in REGION_TYPES else "wall"


def _resolve_model_id() -> str:
    """
    Prefer custom workspace/project when configured; otherwise use public model.
    """
    settings = get_settings()
    workspace = (settings.roboflow_workspace or "").strip()
    project = (settings.roboflow_project or "").strip()
    if (
        workspace
        and project
        and not workspace.startswith("your-")
        and not project.startswith("your-")
    ):
        return f"{workspace}/{project}"
    model = (settings.roboflow_model or "door-window-detection/1").strip()
    return model


async def get_api_usage() -> dict[str, int]:
    """Return Roboflow usage stats: { used, remaining, limit }."""
    settings = get_settings()
    limit = settings.roboflow_monthly_limit
    key = year_month_key()
    doc = await ApiUsage.find_one(ApiUsage.service == "roboflow", ApiUsage.year_month == key)
    used = doc.call_count if doc else 0
    remaining = max(0, limit - used)
    return {"used": used, "remaining": remaining, "limit": limit}


async def _increment_usage() -> dict[str, int]:
    """Atomically bump the monthly Roboflow counter."""
    key = year_month_key()
    doc = await ApiUsage.find_one(ApiUsage.service == "roboflow", ApiUsage.year_month == key)
    if doc is None:
        doc = ApiUsage(service="roboflow", year_month=key, call_count=1)
        await doc.insert()
    else:
        doc.call_count += 1
        doc.updated_at = datetime.now(timezone.utc)
        await doc.save()
    return await get_api_usage()


def _opencv_fallback(image_bytes: bytes) -> list[Segment]:
    """Basic contour-based segmentation when Roboflow is unavailable or limited."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        return []

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    kernel = np.ones((5, 5), np.uint8)
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = (width * height) * 0.01
    max_area = (width * height) * 0.85
    candidates = [c for c in contours if min_area < cv2.contourArea(c) < max_area]
    candidates = sorted(candidates, key=cv2.contourArea, reverse=True)[:8]

    segments: list[Segment] = []
    type_counts: dict[str, int] = {}
    for contour in candidates:
        x, y, w, h = cv2.boundingRect(contour)
        area = int(cv2.contourArea(contour))
        aspect = w / h if h else 1.0
        cy = y + h / 2

        if aspect > 2.2 and cy < height * 0.35:
            region = "roof_edge"
        elif aspect < 0.45 and h > height * 0.25:
            region = "pillar"
        elif 0.6 <= aspect <= 1.6 and area < (width * height) * 0.08:
            region = "window" if cy < height * 0.7 else "door"
        elif aspect > 1.8 and cy > height * 0.55:
            region = "balcony"
        else:
            region = "wall"

        type_counts[region] = type_counts.get(region, 0) + 1
        idx = type_counts[region]
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, thickness=-1)
        ok, encoded = cv2.imencode(".png", mask)
        mask_b64 = base64.b64encode(encoded.tobytes()).decode("ascii") if ok else ""

        segments.append(
            Segment(
                id=str(uuid.uuid4()),
                label=f"{region}_{idx}",
                region_type=region,
                mask_data=mask_b64,
                pixel_area=area,
                bbox=[int(x), int(y), int(w), int(h)],
                confidence=0.45,
            )
        )

    if not segments:
        segments.append(
            Segment(
                id=str(uuid.uuid4()),
                label="wall_1",
                region_type="wall",
                mask_data="",
                pixel_area=int(width * height * 0.6),
                bbox=[
                    int(width * 0.1),
                    int(height * 0.15),
                    int(width * 0.8),
                    int(height * 0.7),
                ],
                confidence=0.3,
            )
        )
    return segments


def _iou(a: list[int], b: list[int]) -> float:
    """IoU for [x, y, w, h] boxes."""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def _merge_segments(primary: list[Segment], secondary: list[Segment]) -> list[Segment]:
    """Keep Roboflow detections and add non-overlapping OpenCV structure regions."""
    merged = list(primary)
    for seg in secondary:
        # Prefer structure classes from OpenCV when Roboflow only found windows/doors
        if seg.region_type not in {"wall", "roof_edge", "pillar", "parapet", "balcony", "railing", "gate"}:
            continue
        overlaps = any(_iou(seg.bbox, existing.bbox) > 0.35 for existing in merged if existing.bbox)
        if not overlaps:
            merged.append(seg)

    # Ensure at least one wall exists for material assignment
    if not any(s.region_type == "wall" for s in merged) and secondary:
        wall = next((s for s in secondary if s.region_type == "wall"), None)
        if wall:
            merged.insert(0, wall)
    return merged


async def _download_image(image_url: str) -> bytes:
    """Download image bytes from a URL."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(image_url)
        response.raise_for_status()
        return response.content


async def _call_roboflow(image_bytes: bytes) -> list[dict[str, Any]]:
    """Call Roboflow Serverless API; returns raw predictions list."""
    settings = get_settings()
    api_key = settings.roboflow_api_key
    if not api_key:
        raise RuntimeError("ROBOFLOW_API_KEY is not configured")

    model_id = _resolve_model_id()
    url = f"https://serverless.roboflow.com/{model_id}"
    params = {"api_key": api_key}

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            url,
            params=params,
            files={"file": ("house.jpg", image_bytes, "image/jpeg")},
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Roboflow error {response.status_code} ({model_id}): {response.text[:200]}"
            )
        data = response.json()
    return data.get("predictions") or []


def _predictions_to_segments(
    predictions: list[dict[str, Any]], image_shape: tuple[int, int]
) -> list[Segment]:
    """Convert Roboflow predictions into Segment models."""
    height, width = image_shape
    type_counts: dict[str, int] = {}
    segments: list[Segment] = []

    for pred in predictions:
        region = _normalize_region_type(pred.get("class") or pred.get("class_name") or "wall")
        type_counts[region] = type_counts.get(region, 0) + 1
        idx = type_counts[region]

        cx = float(pred.get("x", 0))
        cy = float(pred.get("y", 0))
        w = float(pred.get("width", 0))
        h = float(pred.get("height", 0))
        x = max(0, int(cx - w / 2))
        y = max(0, int(cy - h / 2))
        bw = max(1, int(w))
        bh = max(1, int(h))
        pixel_area = int(bw * bh)

        mask_b64 = ""
        points = pred.get("points")
        if points:
            mask = np.zeros((height, width), dtype=np.uint8)
            pts = np.array([[int(p["x"]), int(p["y"])] for p in points], dtype=np.int32)
            if len(pts) >= 3:
                cv2.fillPoly(mask, [pts], 255)
                pixel_area = int(cv2.countNonZero(mask))
                ok, encoded = cv2.imencode(".png", mask)
                if ok:
                    mask_b64 = base64.b64encode(encoded.tobytes()).decode("ascii")

        segments.append(
            Segment(
                id=str(uuid.uuid4()),
                label=f"{region}_{idx}",
                region_type=region,
                mask_data=mask_b64,
                pixel_area=pixel_area,
                bbox=[x, y, bw, bh],
                confidence=float(pred.get("confidence", 0.5)),
            )
        )
    return segments


async def segment_building(image_url: str) -> tuple[list[Segment], dict[str, Any]]:
    """
    Segment a building image via Roboflow + OpenCV structure merge.

    Returns (segments, meta) where meta includes usage + source + warnings.
    """
    settings = get_settings()
    usage = await get_api_usage()
    warnings: list[str] = []
    source = "opencv_fallback"
    model_id = _resolve_model_id()

    if usage["remaining"] < settings.roboflow_warn_threshold:
        warnings.append(
            f"Roboflow free tier low: {usage['remaining']}/{usage['limit']} calls remaining this month."
        )

    image_bytes = await _download_image(image_url)
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    shape = image.shape[:2] if image is not None else (1, 1)
    opencv_segments = _opencv_fallback(image_bytes)

    segments: list[Segment] = []
    if usage["remaining"] <= 0:
        warnings.append("Roboflow monthly limit reached. Using OpenCV fallback segmentation.")
        segments = opencv_segments
    else:
        try:
            predictions = await _call_roboflow(image_bytes)
            await _increment_usage()
            usage = await get_api_usage()
            rf_segments = _predictions_to_segments(predictions, shape)
            if rf_segments:
                segments = _merge_segments(rf_segments, opencv_segments)
                source = f"roboflow:{model_id}+opencv"
            else:
                warnings.append("Roboflow returned no detections. Using OpenCV fallback.")
                segments = opencv_segments
                source = "opencv_fallback"
        except Exception as exc:
            warnings.append(f"Roboflow unavailable ({exc}). Using OpenCV fallback.")
            segments = opencv_segments
            source = "opencv_fallback"

    meta = {"usage": usage, "source": source, "warnings": warnings, "model": model_id}
    return segments, meta
