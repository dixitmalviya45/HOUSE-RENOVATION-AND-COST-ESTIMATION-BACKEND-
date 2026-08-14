"""Estimate request/response schemas — Phase 6+."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ReferenceInput(BaseModel):
    """Reference measurement for area scaling."""

    segment_id: str
    dimension: str  # height | width
    value_feet: float


class AreaRequest(BaseModel):
    """Request to calculate segment areas."""

    project_id: str
    reference: ReferenceInput


class CustomRateItem(BaseModel):
    """Optional per-segment rate override."""

    segment_id: str
    custom_rate: float


class CostRequest(BaseModel):
    """Request to calculate cost estimate."""

    project_id: str
    custom_rates: Optional[List[CustomRateItem]] = None


class CostLineItemResponse(BaseModel):
    """Cost line item for API responses."""

    segment_id: str
    segment_label: str
    region_type: str
    material_name: str
    area_sqft: float
    material_qty_with_wastage: float
    wastage_percent: float
    material_cost: float
    labor_cost: float
    total_cost: float


class EstimateResponse(BaseModel):
    """Full estimate response."""

    id: str
    project_id: str
    line_items: List[CostLineItemResponse]
    total_material_cost: float
    total_labor_cost: float
    grand_total: float
    created_at: datetime
