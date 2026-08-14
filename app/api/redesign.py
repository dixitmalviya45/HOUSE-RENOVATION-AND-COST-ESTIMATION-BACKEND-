"""AI redesign routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.schemas.project import project_to_response
from app.services import ai_generation
from app.utils.project_helpers import get_user_project, touch_project

router = APIRouter(prefix="/redesign", tags=["redesign"])


class RedesignRequest(BaseModel):
    project_id: str


class RedesignSelectRequest(BaseModel):
    project_id: str
    selected_url: str


@router.post("")
async def generate_redesign(
    payload: RedesignRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Generate redesigned house images via Gemini (with local fallback)."""
    project = await get_user_project(payload.project_id, current_user)
    try:
        result = await ai_generation.generate_redesign(project)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Redesign failed: {exc}",
        ) from exc

    urls = result["urls"]
    project.redesigned_image_urls = urls
    project.selected_redesign_url = urls[0] if urls else None
    project.status = "redesigned"
    touch_project(project)
    await project.save()
    return {
        "redesigned_image_urls": urls,
        "project": project_to_response(project),
        "source": result.get("source"),
        "warning": result.get("warning"),
    }


@router.post("/select")
async def select_redesign(
    payload: RedesignSelectRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Select a preferred redesign variation."""
    project = await get_user_project(payload.project_id, current_user)
    if payload.selected_url not in (project.redesigned_image_urls or []):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected URL is not one of the generated redesigns",
        )
    project.selected_redesign_url = payload.selected_url
    touch_project(project)
    await project.save()
    return {"project": project_to_response(project)}
