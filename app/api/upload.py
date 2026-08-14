"""Image upload routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.schemas.project import ProjectResponse, project_to_response
from app.services import cloudinary_service, image_processing
from app.utils.project_helpers import get_user_project, touch_project

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
MAX_BYTES = 10 * 1024 * 1024


@router.post("", response_model=dict)
async def upload_image(
    project_id: str = Form(...),
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Validate image quality with OpenCV, preprocess/compress,
    upload to Cloudinary, and attach URLs to the project.
    """
    project = await get_user_project(project_id, current_user)

    content_type = (image.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only JPG, PNG, and WEBP images are allowed",
        )

    raw = await image.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Empty image file",
        )
    if len(raw) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Image must be 10MB or smaller",
        )

    quality_report = image_processing.validate_image_quality(raw)
    if not quality_report["is_valid"]:
        return {
            "image_url": None,
            "quality_report": quality_report,
            "project": project_to_response(project),
            "accepted": False,
        }

    try:
        processed = image_processing.preprocess_image(raw)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to process image: {exc}",
        ) from exc

    uploaded = cloudinary_service.upload_image(processed, folder=f"e2m/{project_id}")
    image_url = uploaded["secure_url"]

    project.original_image_url = image_url
    project.preprocessed_image_url = image_url
    project.status = "uploaded"
    project.segments = []
    project.material_selections = []
    project.redesigned_image_urls = []
    project.selected_redesign_url = None
    project.area_calculations = []
    project.reference_measurement = None
    touch_project(project)
    await project.save()

    return {
        "image_url": image_url,
        "quality_report": quality_report,
        "project": project_to_response(project),
        "accepted": True,
    }
