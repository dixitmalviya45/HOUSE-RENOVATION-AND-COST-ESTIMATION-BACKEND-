"""Local free redesign fallback when Gemini image quota is unavailable."""

from __future__ import annotations

import colorsys
import hashlib
import io
import math
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


# Distinct, saturated facade colors so changes are obvious in the UI
MATERIAL_COLORS: dict[str, tuple[int, int, int]] = {
    # Paints
    "royal exterior emulsion": (92, 124, 250),
    "ace exterior emulsion": (226, 232, 240),
    "apex ultima weather proof": (14, 165, 233),
    "texture paint rustic": (180, 120, 70),
    "metallic finish paint": (148, 163, 184),
    # Tiles
    "ceramic wall tile 300x600": (234, 179, 8),
    "porcelain tile 600x600": (248, 250, 252),
    "mosaic tile pattern": (236, 72, 153),
    "subway tile white": (241, 245, 249),
    # Cladding
    "natural stone cladding": (120, 113, 108),
    "italian marble cladding": (226, 232, 240),
    "slate cladding": (71, 85, 105),
    "brick veneer": (185, 68, 52),
    "wpc wall cladding": (146, 104, 60),
    # Texture / panels
    "sand finish texture": (212, 176, 130),
    "roller texture": (190, 160, 120),
    "knockdown texture": (168, 140, 100),
    "acp panels": (55, 65, 81),
    "hpl panels": (30, 41, 59),
}

CATEGORY_FALLBACK = {
    "paint": (99, 102, 241),
    "tiles": (245, 158, 11),
    "cladding": (120, 113, 108),
    "railing": (148, 163, 184),
    "texture": (212, 176, 130),
    "panels": (51, 65, 85),
}

WALL_LIKE = {"wall", "parapet", "pillar", "roof_edge", "balcony"}


def _infer_category(material_name: str, category: str | None = None) -> str:
    if category:
        return category.lower()
    name = (material_name or "").lower()
    if any(k in name for k in ("paint", "emulsion", "apex", "ace", "metallic")):
        return "paint"
    if any(k in name for k in ("tile", "mosaic", "subway", "porcelain", "ceramic")):
        return "tiles"
    if any(k in name for k in ("cladding", "stone", "marble", "brick", "slate", "wpc")):
        return "cladding"
    if any(k in name for k in ("railing", "steel", "iron", "aluminum", "glass")):
        return "railing"
    if any(k in name for k in ("texture", "sand", "roller", "knockdown")):
        return "texture"
    if any(k in name for k in ("panel", "acp", "hpl")):
        return "panels"
    return "paint"


def _color_for_material(material_name: str, category: str | None = None) -> tuple[int, int, int]:
    """Return a vivid RGB color for the material."""
    key = (material_name or "").strip().lower()
    if key in MATERIAL_COLORS:
        return MATERIAL_COLORS[key]
    cat = _infer_category(material_name, category)
    base = CATEGORY_FALLBACK.get(cat, (99, 102, 241))
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    r, g, b = [c / 255.0 for c in base]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h = (h + int(digest[:2], 16) / 255.0 * 0.12) % 1.0
    s = min(0.85, max(0.35, s))
    v = min(0.95, max(0.35, v))
    nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
    return int(nr * 255), int(ng * 255), int(nb * 255)


def _clip_bbox(bbox: list[int], width: int, height: int) -> tuple[int, int, int, int] | None:
    if not bbox or len(bbox) < 4:
        return None
    x, y, bw, bh = [int(v) for v in bbox[:4]]
    # If Roboflow coords were for a larger canvas, scale down
    max_x, max_y = x + bw, y + bh
    if max_x > width * 1.05 or max_y > height * 1.05:
        scale = min(width / max(max_x, 1), height / max(max_y, 1))
        x, y, bw, bh = int(x * scale), int(y * scale), int(bw * scale), int(bh * scale)
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(width, x + bw), min(height, y + bh)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    return x1, y1, x2, y2


def _make_pattern(h: int, w: int, color: tuple[int, int, int], category: str, variation: int) -> np.ndarray:
    """Create a BGR pattern patch for the material category."""
    bgr = (color[2], color[1], color[0])
    patch = np.zeros((h, w, 3), dtype=np.uint8)
    patch[:, :] = bgr

    if category == "tiles":
        step = max(12, min(h, w) // 10)
        for i in range(0, h, step):
            cv2.line(patch, (0, i), (w, i), (255, 255, 255), 1)
        for j in range(0, w, step):
            cv2.line(patch, (j, 0), (j, h), (255, 255, 255), 1)
    elif category == "cladding":
        step = max(8, min(h, w) // 14)
        for i in range(0, h, step):
            shade = tuple(max(0, min(255, c + ((-1) ** (i // step)) * 18)) for c in bgr)
            cv2.rectangle(patch, (0, i), (w, i + step - 1), shade, -1)
    elif category == "panels":
        step_w = max(40, w // 5)
        for j in range(0, w, step_w):
            shade = tuple(max(0, min(255, c + ((-1) ** (j // step_w)) * 22)) for c in bgr)
            cv2.rectangle(patch, (j, 0), (j + step_w - 2, h), shade, -1)
            cv2.line(patch, (j, 0), (j, h), (220, 220, 220), 2)
    elif category == "texture":
        noise = np.random.default_rng(variation + 7).integers(0, 40, (h, w, 1), dtype=np.int16)
        base = patch.astype(np.int16)
        patch = np.clip(base + noise, 0, 255).astype(np.uint8)
    elif category == "railing":
        patch[:, :] = (40, 40, 40)
        for j in range(8, w, 18):
            cv2.line(patch, (j, 0), (j, h), bgr, 3)
        cv2.line(patch, (0, h // 3), (w, h // 3), bgr, 3)
        cv2.line(patch, (0, 2 * h // 3), (w, 2 * h // 3), bgr, 3)
    else:
        # paint: soft vertical gradient
        for i in range(h):
            factor = 0.85 + 0.3 * (i / max(h - 1, 1))
            if variation:
                factor = 1.15 - 0.3 * (i / max(h - 1, 1))
            row = tuple(max(0, min(255, int(c * factor))) for c in bgr)
            patch[i, :] = row

    return patch


def _apply_material(
    image: np.ndarray,
    bbox: list[int],
    color: tuple[int, int, int],
    category: str,
    variation: int,
    alpha: float,
) -> None:
    """Blend a strong material pattern into the region."""
    h, w = image.shape[:2]
    box = _clip_bbox(bbox, w, h)
    if box is None:
        return
    x1, y1, x2, y2 = box
    roi = image[y1:y2, x1:x2]
    pattern = _make_pattern(roi.shape[0], roi.shape[1], color, category, variation)

    # Preserve structure: keep some luminance from original
    orig = roi.astype(np.float32)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    lum = 0.55 + 0.45 * gray
    patterned = pattern.astype(np.float32)
    patterned *= lum[..., None]

    blended = orig * (1.0 - alpha) + patterned * alpha
    roi[:] = np.clip(blended, 0, 255).astype(np.uint8)

    # Outline so the changed region is obvious
    cv2.rectangle(image, (x1, y1), (x2 - 1, y2 - 1), (color[2], color[1], color[0]), 2)


def _expand_assignments(project: Any) -> list[tuple[Any, str, tuple[int, int, int], str]]:
    """
    Build (segment, material_name, color, category) assignments.

    If the user only tagged one facade material, also apply it to other wall-like
    segments that have no material yet so the house clearly changes.
    """
    segment_map = {s.id: s for s in (project.segments or [])}
    assigned: dict[str, tuple[str, tuple[int, int, int], str]] = {}

    for sel in project.material_selections or []:
        segment = segment_map.get(sel.segment_id)
        if segment is None:
            continue
        category = _infer_category(sel.material_name)
        color = _color_for_material(sel.material_name, category)
        assigned[segment.id] = (sel.material_name, color, category)

    # Propagate a facade material onto unassigned wall-like regions
    facade_pick = None
    for sel in project.material_selections or []:
        cat = _infer_category(sel.material_name)
        if cat in {"paint", "tiles", "cladding", "texture", "panels"}:
            facade_pick = (
                sel.material_name,
                _color_for_material(sel.material_name, cat),
                cat,
            )
            break

    if facade_pick:
        for segment in project.segments or []:
            if segment.id in assigned:
                continue
            if segment.region_type in WALL_LIKE:
                assigned[segment.id] = facade_pick

    # If somehow nothing matched, tint the largest segment
    if not assigned and project.segments and project.material_selections:
        largest = max(project.segments, key=lambda s: s.pixel_area or 0)
        sel = project.material_selections[0]
        cat = _infer_category(sel.material_name)
        assigned[largest.id] = (
            sel.material_name,
            _color_for_material(sel.material_name, cat),
            cat,
        )

    rows = []
    for segment in project.segments or []:
        if segment.id not in assigned:
            continue
        name, color, category = assigned[segment.id]
        rows.append((segment, name, color, category))
    return rows


def generate_local_redesign(image_bytes: bytes, project: Any, variation: int = 0) -> bytes:
    """
    Create a clearly visible free local material preview.

    Used when Gemini image-generation quota is unavailable.
    """
    pil = Image.open(io.BytesIO(image_bytes))
    if pil.mode != "RGB":
        pil = pil.convert("RGB")

    image = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    alpha = 0.72 if variation == 0 else 0.82

    assignments = _expand_assignments(project)
    legend_items: list[str] = []
    for segment, name, color, category in assignments:
        _apply_material(image, segment.bbox or [], color, category, variation, alpha)
        legend_items.append(f"{segment.label}: {name}")

    # Whole-image grade so even empty assignments still look different
    if variation == 0:
        image = cv2.convertScaleAbs(image, alpha=1.08, beta=8)
    else:
        image = cv2.convertScaleAbs(image, alpha=1.12, beta=-4)

    out = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    result = Image.fromarray(out)
    draw = ImageDraw.Draw(result)

    # Header banner
    header_h = 34
    draw.rectangle((0, 0, result.width, header_h), fill=(15, 23, 42))
    draw.text(
        (12, 9),
        "Material preview (local) — Gemini image quota unavailable",
        fill=(199, 210, 254),
    )

    # Legend of applied materials
    if legend_items:
        box_h = 18 + 16 * min(len(legend_items), 6)
        draw.rectangle(
            (8, header_h + 8, min(result.width - 8, 420), header_h + 8 + box_h),
            fill=(15, 23, 42, 180) if result.mode == "RGBA" else (30, 41, 59),
        )
        y = header_h + 14
        for item in legend_items[:6]:
            draw.text((16, y), item[:48], fill=(226, 232, 240))
            y += 16

    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue()
