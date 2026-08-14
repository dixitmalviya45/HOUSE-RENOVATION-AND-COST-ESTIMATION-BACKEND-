"""Estimate Beanie document with embedded cost line items."""

from datetime import datetime, timezone
from typing import List

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field


class CostLineItem(BaseModel):
    """Single line in a renovation cost estimate."""

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


class Estimate(Document):
    """Full cost estimate for a project."""

    project_id: PydanticObjectId
    user_id: PydanticObjectId
    line_items: List[CostLineItem] = Field(default_factory=list)
    total_material_cost: float = 0.0
    total_labor_cost: float = 0.0
    grand_total: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "estimates"
