"""Segmentation API routes."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.middleware.auth_middleware import get_current_user
from app.models.project import Segment
from app.models.user import User
from app.schemas.project import SegmentSchema, project_to_response
from app.services import segmentation as segmentation_service
from app.utils.project_helpers import get_user_project, touch_project

router = APIRouter(prefix="/segment", tags=["segmentation"])


class SegmentRequest(BaseModel):
    """Trigger segmentation for a project."""

    project_id: str


class SegmentUpdateRequest(BaseModel):
    """User corrections to segment labels/regions."""

    segments: List[SegmentSchema] = Field(default_factory=list)


@router.get("/usage")
async def api_usage(current_user: User = Depends(get_current_user)) -> dict:
    """Return Roboflow monthly usage for the dashboard indicator."""
    return await segmentation_service.get_api_usage()


@router.post("")
async def segment_image(
    payload: SegmentRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Run Roboflow (or OpenCV fallback) segmentation for a project image."""
    project = await get_user_project(payload.project_id, current_user)
    image_url = project.preprocessed_image_url or project.original_image_url
    if not image_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Upload a house photo before running segmentation",
        )

    try:
        segments, meta = await segmentation_service.segment_building(image_url)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Segmentation failed: {exc}",
        ) from exc

    project.segments = segments
    project.status = "segmented"
    touch_project(project)
    await project.save()

    return {
        "segments": [SegmentSchema(**s.model_dump()) for s in segments],
        "project": project_to_response(project),
        "usage": meta["usage"],
        "source": meta["source"],
        "warnings": meta["warnings"],
    }


@router.patch("/{project_id}")
async def update_segments(
    project_id: str,
    payload: SegmentUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Apply user corrections to segments."""
    project = await get_user_project(project_id, current_user)
    project.segments = [Segment(**s.model_dump()) for s in payload.segments]
    if project.segments:
        project.status = "segmented"
    touch_project(project)
    await project.save()
    return {
        "segments": [SegmentSchema(**s.model_dump()) for s in project.segments],
        "project": project_to_response(project),
    }
