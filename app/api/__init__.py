"""API routers package."""

from app.api import (
    auth,
    projects,
    upload,
    segmentation,
    materials,
    redesign,
    estimation,
    report,
)

__all__ = [
    "auth",
    "projects",
    "upload",
    "segmentation",
    "materials",
    "redesign",
    "estimation",
    "report",
]
