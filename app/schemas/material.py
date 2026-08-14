"""Material request/response schemas — Phase 4+."""

from typing import List, Optional

from pydantic import BaseModel


class MaterialResponse(BaseModel):
    """Material catalog item."""

    id: str
    name: str
    category: str
    applicable_to: List[str]
    texture_image_url: str
    rate_per_sqft: float
    coverage_per_unit: float
    wastage_percent: float
    labor_rate_per_sqft: float
    durability: str
    maintenance: str
    description: Optional[str] = None


class MaterialSelectionItem(BaseModel):
    """Assign a material to a segment."""

    segment_id: str
    material_id: str


class MaterialSelectRequest(BaseModel):
    """Bulk material selection for a project."""

    project_id: str
    selections: List[MaterialSelectionItem]
