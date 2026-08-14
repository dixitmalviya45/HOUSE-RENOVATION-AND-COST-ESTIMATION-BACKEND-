"""Project CRUD routes."""

from fastapi import APIRouter, Depends, status

from app.middleware.auth_middleware import get_current_user
from app.models.project import Project
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectListItem,
    ProjectResponse,
    ProjectUpdate,
    project_to_list_item,
    project_to_response,
)
from app.utils.project_helpers import get_user_project, touch_project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """Create a new renovation project for the current user."""
    project = Project(
        user_id=current_user.id,
        name=payload.name.strip(),
        status="uploaded",
    )
    await project.insert()
    return project_to_response(project)


@router.get("", response_model=list[ProjectListItem])
async def list_projects(
    current_user: User = Depends(get_current_user),
) -> list[ProjectListItem]:
    """List the current user's projects (newest first)."""
    projects = (
        await Project.find(Project.user_id == current_user.id)
        .sort(-Project.created_at)
        .to_list()
    )
    return [project_to_list_item(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """Get full project detail."""
    project = await get_user_project(project_id, current_user)
    return project_to_response(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """Update project name, status, or selected redesign."""
    project = await get_user_project(project_id, current_user)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(project, key, value)
    touch_project(project)
    await project.save()
    return project_to_response(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a project owned by the current user."""
    project = await get_user_project(project_id, current_user)
    await project.delete()
