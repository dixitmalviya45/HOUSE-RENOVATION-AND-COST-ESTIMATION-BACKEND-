"""Shared helpers for loading and authorizing projects."""

from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException, status

from app.models.project import Project
from app.models.user import User


def touch_project(project: Project) -> None:
    """Update the project's updated_at timestamp."""
    project.updated_at = datetime.now(timezone.utc)


async def get_user_project(project_id: str, user: User) -> Project:
    """Load a project owned by the current user or raise 404."""
    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    project = await Project.get(project_id)
    if project is None or str(project.user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project
