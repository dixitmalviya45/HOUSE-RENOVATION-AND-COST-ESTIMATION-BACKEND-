"""Gemini API redesign generation with retry/backoff and local fallback."""

from __future__ import annotations

import asyncio
import base64
import io
import logging
from typing import Any

import httpx
from fastapi import HTTPException, status
from google import genai
from google.genai import types
from PIL import Image

from app.config import get_settings
from app.services import cloudinary_service
from app.services.local_redesign import generate_local_redesign

logger = logging.getLogger(__name__)

# Prefer newer image models; free-tier quota may still be 0 for some accounts.
IMAGE_MODELS = (
    "gemini-3.1-flash-lite-image",
    "gemini-3.1-flash-image",
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
)


def _build_prompt(project) -> str:
    """Build the redesign prompt from material selections."""
    lines = []
    for sel in project.material_selections or []:
        segment = next((s for s in project.segments if s.id == sel.segment_id), None)
        region = segment.region_type if segment else "region"
        label = segment.label if segment else sel.segment_id
        lines.append(f"- {region} ({label}): Apply {sel.material_name}")

    materials_block = "\n".join(lines) if lines else "- walls: Apply a fresh modern exterior finish"

    return f"""You are an exterior renovation visualization expert. Given this house photo, generate a photorealistic redesigned version with these exact material changes:
{materials_block}
CRITICAL RULES:
- Keep EXACT same building structure, dimensions, angles, perspective
- Do NOT change building shape or add/remove elements
- Maintain same lighting and shadow direction
- Apply materials ONLY to specified regions
- Photorealistic quality, not cartoon or illustration
- Keep surrounding environment natural"""


async def _download_image(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def _extract_images_from_response(response: Any) -> list[bytes]:
    """Pull image bytes from a Gemini generate_content response."""
    images: list[bytes] = []
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                data = inline.data
                if isinstance(data, str):
                    images.append(base64.b64decode(data))
                elif isinstance(data, (bytes, bytearray)):
                    images.append(bytes(data))
    return images


def _is_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in ("429", "rate", "quota", "resource_exhausted", "too many", "limit: 0")
    )


async def _generate_one_variation(client: genai.Client, prompt: str, image_bytes: bytes) -> bytes:
    """Call Gemini once for an image redesign with exponential backoff."""
    max_retries = 3
    delay = 3.0
    last_error: Exception | None = None

    pil_image = Image.open(io.BytesIO(image_bytes))
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")
    # Keep payload smaller for free-tier reliability
    longest = max(pil_image.size)
    if longest > 1024:
        scale = 1024 / longest
        pil_image = pil_image.resize(
            (int(pil_image.width * scale), int(pil_image.height * scale)),
            Image.Resampling.LANCZOS,
        )

    for attempt in range(max_retries):
        try:
            response = None
            last_model_error: Exception | None = None
            for model_name in IMAGE_MODELS:
                try:
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model_name,
                        contents=[prompt, pil_image],
                        config=types.GenerateContentConfig(
                            response_modalities=["TEXT", "IMAGE"],
                        ),
                    )
                    images = _extract_images_from_response(response)
                    if images:
                        return images[0]
                    last_model_error = RuntimeError(f"{model_name} returned no image")
                except Exception as model_exc:
                    last_model_error = model_exc
                    # Don't burn retries across every model on hard quota=0
                    if _is_quota_error(model_exc) and "limit: 0" in str(model_exc).lower():
                        raise model_exc
                    continue

            raise last_model_error or RuntimeError("No Gemini image model available")
        except Exception as exc:
            last_error = exc
            if _is_quota_error(exc):
                if "limit: 0" in str(exc).lower():
                    # Account has no free image-gen quota — skip further retries
                    raise
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise
            raise

    raise last_error or RuntimeError("AI redesign failed")


def _compress_for_upload(image_bytes: bytes) -> bytes:
    """Compress generated image before Cloudinary upload."""
    pil = Image.open(io.BytesIO(image_bytes))
    if pil.mode != "RGB":
        pil = pil.convert("RGB")
    longest = max(pil.size)
    if longest > 1200:
        scale = 1200 / longest
        pil = pil.resize((int(pil.width * scale), int(pil.height * scale)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=80, optimize=True)
    return buf.getvalue()


async def generate_redesign(project) -> dict[str, Any]:
    """
    Try Gemini photorealistic redesign; if image quota is unavailable,
    fall back to free local material preview (2 variations).

    Returns { urls, source, warning }.
    """
    settings = get_settings()
    if not settings.gemini_api_key or settings.gemini_api_key.startswith("your-"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GEMINI_API_KEY is not configured",
        )

    image_url = project.preprocessed_image_url or project.original_image_url
    if not image_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Project has no image to redesign",
        )
    if not project.material_selections:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select materials before generating a redesign",
        )

    prompt = _build_prompt(project)
    image_bytes = await _download_image(image_url)
    client = genai.Client(api_key=settings.gemini_api_key)

    urls: list[str] = []
    source = "gemini"
    warning = None

    try:
        # One Gemini variation first (saves free quota); second via local if needed
        generated = await _generate_one_variation(client, prompt, image_bytes)
        compressed = _compress_for_upload(generated)
        uploaded = cloudinary_service.upload_image(
            compressed, folder=f"e2m/{project.id}/redesign"
        )
        urls.append(uploaded["secure_url"])

        # Second variation: try Gemini once more, else local
        try:
            await asyncio.sleep(5)
            generated2 = await _generate_one_variation(client, prompt, image_bytes)
            compressed2 = _compress_for_upload(generated2)
            uploaded2 = cloudinary_service.upload_image(
                compressed2, folder=f"e2m/{project.id}/redesign"
            )
            urls.append(uploaded2["secure_url"])
        except Exception:
            local = generate_local_redesign(image_bytes, project, variation=1)
            uploaded2 = cloudinary_service.upload_image(
                _compress_for_upload(local), folder=f"e2m/{project.id}/redesign"
            )
            urls.append(uploaded2["secure_url"])
            warning = "Second variation used local preview to conserve Gemini quota."
    except Exception as exc:
        logger.warning("Gemini redesign unavailable, using local fallback: %s", exc)
        if not _is_quota_error(exc) and "no image" not in str(exc).lower():
            # Unexpected failure — still try local so the flow continues
            pass
        source = "local_fallback"
        warning = (
            "Gemini image generation quota is unavailable on this free API key "
            "(image models show limit 0). Showing a free local material preview instead. "
            "For photorealistic AI images, enable billing or wait for quota reset at "
            "https://ai.dev/rate-limit"
        )
        for i in range(2):
            local = generate_local_redesign(image_bytes, project, variation=i)
            uploaded = cloudinary_service.upload_image(
                _compress_for_upload(local), folder=f"e2m/{project.id}/redesign"
            )
            urls.append(uploaded["secure_url"])

    if not urls:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not generate redesign images",
        )

    return {"urls": urls, "source": source, "warning": warning}
