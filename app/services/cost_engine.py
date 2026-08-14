"""Material + labor cost estimation engine."""

from __future__ import annotations

from bson import ObjectId
from fastapi import HTTPException, status

from app.models.estimate import CostLineItem, Estimate
from app.models.material import Material


async def calculate_cost(project, custom_rates: list | None = None) -> Estimate:
    """
    Build Estimate from material selections and area calculations.

    material_qty = area / coverage_per_unit
    wastage applied, then material_cost + labor_cost.
    """
    if not project.material_selections:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select materials before calculating cost",
        )
    if not project.area_calculations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Calculate areas before estimating cost",
        )

    rate_overrides = {
        item.segment_id: item.custom_rate
        for item in (custom_rates or [])
        if getattr(item, "custom_rate", None) is not None
    }

    area_by_segment = {a.segment_id: a for a in project.area_calculations}
    line_items: list[CostLineItem] = []
    total_material = 0.0
    total_labor = 0.0

    for selection in project.material_selections:
        area_row = area_by_segment.get(selection.segment_id)
        if area_row is None:
            continue

        material = None
        if ObjectId.is_valid(selection.material_id):
            material = await Material.get(selection.material_id)
        if material is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Material not found for segment {selection.segment_id}",
            )

        area = float(area_row.area_sqft)
        coverage = material.coverage_per_unit or 1.0
        wastage_percent = float(material.wastage_percent or 0)
        base_rate = rate_overrides.get(selection.segment_id)
        if base_rate is None:
            base_rate = selection.custom_rate if selection.custom_rate is not None else material.rate_per_sqft

        material_qty = area / coverage
        wastage_qty = material_qty * (wastage_percent / 100.0)
        total_qty = material_qty + wastage_qty
        material_cost = round(total_qty * float(base_rate), 2)
        labor_cost = round(area * float(material.labor_rate_per_sqft), 2)
        line_total = round(material_cost + labor_cost, 2)

        total_material += material_cost
        total_labor += labor_cost

        line_items.append(
            CostLineItem(
                segment_id=selection.segment_id,
                segment_label=area_row.segment_label,
                region_type=area_row.region_type,
                material_name=material.name,
                area_sqft=area,
                material_qty_with_wastage=round(total_qty, 3),
                wastage_percent=wastage_percent,
                material_cost=material_cost,
                labor_cost=labor_cost,
                total_cost=line_total,
            )
        )

    estimate = Estimate(
        project_id=project.id,
        user_id=project.user_id,
        line_items=line_items,
        total_material_cost=round(total_material, 2),
        total_labor_cost=round(total_labor, 2),
        grand_total=round(total_material + total_labor, 2),
    )
    await estimate.insert()
    return estimate
