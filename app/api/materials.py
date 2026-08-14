"""Materials catalog routes."""

from __future__ import annotations

from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.middleware.auth_middleware import get_current_user
from app.models.material import Material
from app.models.project import MaterialSelection
from app.models.user import User
from app.schemas.material import MaterialResponse, MaterialSelectRequest
from app.schemas.project import project_to_response
from app.utils.project_helpers import get_user_project, touch_project

router = APIRouter(prefix="/materials", tags=["materials"])


def _to_response(material: Material) -> MaterialResponse:
    return MaterialResponse(
        id=str(material.id),
        name=material.name,
        category=material.category,
        applicable_to=material.applicable_to,
        texture_image_url=material.texture_image_url or "",
        rate_per_sqft=material.rate_per_sqft,
        coverage_per_unit=material.coverage_per_unit,
        wastage_percent=material.wastage_percent,
        labor_rate_per_sqft=material.labor_rate_per_sqft,
        durability=material.durability,
        maintenance=material.maintenance,
        description=material.description,
    )


@router.get("", response_model=list[MaterialResponse])
async def list_materials(
    category: Optional[str] = Query(None),
    applicable_to: Optional[str] = Query(None),
) -> list[MaterialResponse]:
    """List materials, optionally filtered by category or applicable region."""
    query = Material.find_all()
    materials = await query.to_list()
    if category:
        materials = [m for m in materials if m.category == category]
    if applicable_to:
        materials = [m for m in materials if applicable_to in (m.applicable_to or [])]
    return [_to_response(m) for m in materials]


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(material_id: str) -> MaterialResponse:
    """Get a single material by id."""
    if not ObjectId.is_valid(material_id):
        raise HTTPException(status_code=404, detail="Material not found")
    material = await Material.get(material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return _to_response(material)


@router.post("/select")
async def select_materials(
    payload: MaterialSelectRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Save material selections for each segment on a project."""
    project = await get_user_project(payload.project_id, current_user)
    if not project.segments:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Segment the project before selecting materials",
        )

    selections: list[MaterialSelection] = []
    for item in payload.selections:
        if not ObjectId.is_valid(item.material_id):
            raise HTTPException(status_code=422, detail=f"Invalid material id: {item.material_id}")
        material = await Material.get(item.material_id)
        if material is None:
            raise HTTPException(status_code=404, detail=f"Material not found: {item.material_id}")
        selections.append(
            MaterialSelection(
                segment_id=item.segment_id,
                material_id=str(material.id),
                material_name=material.name,
                custom_rate=None,
            )
        )

    project.material_selections = selections
    project.status = "materials_selected"
    touch_project(project)
    await project.save()
    return {"project": project_to_response(project), "selections": [s.model_dump() for s in selections]}
