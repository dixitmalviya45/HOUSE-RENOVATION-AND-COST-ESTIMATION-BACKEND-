"""Cloudinary upload/delivery helpers with free-tier optimizations."""

from __future__ import annotations

import io
from typing import Any

import cloudinary
import cloudinary.api
import cloudinary.uploader
from fastapi import HTTPException, status

from app.config import get_settings

_configured = False


def _ensure_config() -> None:
    """Configure Cloudinary once from settings."""
    global _configured
    if _configured:
        return
    settings = get_settings()
    if not settings.cloudinary_cloud_name or not settings.cloudinary_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloudinary is not configured. Check CLOUDINARY_* env vars.",
        )
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    _configured = True


def upload_image(image_bytes: bytes, folder: str = "e2m") -> dict[str, Any]:
    """
    Upload image with quality=auto, format=auto, max width 1200.

    Returns dict with secure_url and public_id.
    """
    _ensure_config()
    try:
        result = cloudinary.uploader.upload(
            io.BytesIO(image_bytes),
            folder=folder,
            resource_type="image",
            transformation=[
                {"width": 1200, "crop": "limit"},
                {"quality": "auto", "fetch_format": "auto"},
            ],
        )
        return {
            "secure_url": result.get("secure_url", ""),
            "public_id": result.get("public_id", ""),
            "bytes": result.get("bytes", 0),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Image upload failed: {exc}",
        ) from exc


def get_image_url(public_id: str) -> str:
    """Return an optimized delivery URL for a public_id."""
    _ensure_config()
    return cloudinary.CloudinaryImage(public_id).build_url(
        width=1200,
        crop="limit",
        quality="auto",
        fetch_format="auto",
        secure=True,
    )


def delete_image(public_id: str) -> None:
    """Delete an image to save free-tier storage."""
    if not public_id:
        return
    try:
        _ensure_config()
        cloudinary.uploader.destroy(public_id)
    except Exception:
        # Best-effort cleanup — do not fail the request
        pass
