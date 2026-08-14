"""PDF report routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.middleware.auth_middleware import get_current_user
from app.models.estimate import Estimate
from app.models.user import User
from app.services import report_generator
from app.utils.project_helpers import get_user_project, touch_project

router = APIRouter(prefix="/report", tags=["report"])


@router.get("/{project_id}")
async def generate_report(
    project_id: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Generate and download a PDF estimate report."""
    project = await get_user_project(project_id, current_user)
    estimate = (
        await Estimate.find(
            Estimate.project_id == project.id,
            Estimate.user_id == current_user.id,
        )
        .sort(-Estimate.created_at)
        .first_or_none()
    )
    if estimate is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Calculate a cost estimate before generating the report",
        )

    try:
        pdf_bytes = await report_generator.generate_report(project, estimate)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {exc}",
        ) from exc

    project.status = "completed"
    touch_project(project)
    await project.save()

    filename = f"E2M_{project.name.replace(' ', '_')[:40]}_estimate.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
