"""Project Beanie document with embedded renovation state."""

from datetime import datetime, timezone
from typing import List, Optional

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field


class Segment(BaseModel):
    """Embedded building region from segmentation."""

    id: str
    label: str
    region_type: str
    mask_data: str = ""
    pixel_area: int = 0
    bbox: List[int] = Field(default_factory=list)
    confidence: float = 0.0


class MaterialSelection(BaseModel):
    """Material assigned to a segment."""

    segment_id: str
    material_id: str
    material_name: str
    custom_rate: Optional[float] = None


class ReferenceMeasurement(BaseModel):
    """User-provided real-world dimension for scale."""

    segment_id: str
    known_dimension: str  # height | width
    value_feet: float


class AreaCalculation(BaseModel):
    """Computed surface area for a segment."""

    segment_id: str
    segment_label: str
    region_type: str
    area_sqft: float
    pixel_area: int


class Project(Document):
    """User renovation project with embedded workflow data."""

    user_id: PydanticObjectId
    name: str
    status: str = "uploaded"
    original_image_url: str = ""
    preprocessed_image_url: Optional[str] = None
    redesigned_image_urls: List[str] = Field(default_factory=list)
    selected_redesign_url: Optional[str] = None
    segments: List[Segment] = Field(default_factory=list)
    material_selections: List[MaterialSelection] = Field(default_factory=list)
    reference_measurement: Optional[ReferenceMeasurement] = None
    area_calculations: List[AreaCalculation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "projects"
