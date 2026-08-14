"""Area and cost estimation routes."""

from __future__ import annotations

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.middleware.auth_middleware import get_current_user
from app.models.estimate import Estimate
from app.models.project import ReferenceMeasurement
from app.models.user import User
from app.schemas.estimate import (
    AreaRequest,
    CostLineItemResponse,
    CostRequest,
    CustomRateItem,
    EstimateResponse,
)
from app.schemas.project import project_to_response
from app.services import area_calculator, cost_engine
from app.utils.project_helpers import get_user_project, touch_project

router = APIRouter(prefix="/estimate", tags=["estimation"])


def _estimate_response(estimate: Estimate) -> EstimateResponse:
    return EstimateResponse(
        id=str(estimate.id),
        project_id=str(estimate.project_id),
        line_items=[
            CostLineItemResponse(**item.model_dump()) for item in estimate.line_items
        ],
        total_material_cost=estimate.total_material_cost,
        total_labor_cost=estimate.total_labor_cost,
        grand_total=estimate.grand_total,
        created_at=estimate.created_at,
    )


@router.post("/area")
async def calculate_area(
    payload: AreaRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Calculate segment areas from a reference measurement."""
    project = await get_user_project(payload.project_id, current_user)
    reference = ReferenceMeasurement(
        segment_id=payload.reference.segment_id,
        known_dimension=payload.reference.dimension,
        value_feet=payload.reference.value_feet,
    )
    areas = area_calculator.calculate_areas(project, reference)
    project.reference_measurement = reference
    project.area_calculations = areas
    touch_project(project)
    await project.save()
    return {
        "areas": [a.model_dump() for a in areas],
        "project": project_to_response(project),
    }


@router.post("/cost", response_model=EstimateResponse)
async def calculate_cost(
    payload: CostRequest,
    current_user: User = Depends(get_current_user),
) -> EstimateResponse:
    """Calculate cost breakdown and save estimate."""
    project = await get_user_project(payload.project_id, current_user)
    estimate = await cost_engine.calculate_cost(project, payload.custom_rates)
    project.status = "estimated"
    touch_project(project)
    await project.save()
    return _estimate_response(estimate)


@router.patch("/cost/{estimate_id}", response_model=EstimateResponse)
async def update_cost(
    estimate_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
) -> EstimateResponse:
    """Recalculate cost with modified rates."""
    if not ObjectId.is_valid(estimate_id):
        raise HTTPException(status_code=404, detail="Estimate not found")
    existing = await Estimate.get(estimate_id)
    if existing is None or str(existing.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Estimate not found")

    project = await get_user_project(str(existing.project_id), current_user)
    modified = payload.get("modified_rates") or payload.get("custom_rates") or []
    custom_rates = [
        CustomRateItem(segment_id=item["segment_id"], custom_rate=float(item["custom_rate"]))
        for item in modified
        if "segment_id" in item and "custom_rate" in item
    ]
    estimate = await cost_engine.calculate_cost(project, custom_rates)
    return _estimate_response(estimate)


@router.get("/latest/{project_id}", response_model=EstimateResponse | None)
async def latest_estimate(
    project_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return the most recent estimate for a project, if any."""
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
        return None
    return _estimate_response(estimate)
