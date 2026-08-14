"""Project request/response schemas."""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Create a new renovation project."""

    name: str = Field(..., min_length=1, max_length=200)


class ProjectUpdate(BaseModel):
    """Partial project update."""

    name: Optional[str] = None
    status: Optional[str] = None
    selected_redesign_url: Optional[str] = None


class SegmentSchema(BaseModel):
    """Segment payload for API responses / corrections."""

    id: str
    label: str
    region_type: str
    mask_data: str = ""
    pixel_area: int = 0
    bbox: List[int] = Field(default_factory=list)
    confidence: float = 0.0


class MaterialSelectionSchema(BaseModel):
    """Material assigned to a segment."""

    segment_id: str
    material_id: str
    material_name: str
    custom_rate: Optional[float] = None


class ReferenceMeasurementSchema(BaseModel):
    """Reference measurement embedded on a project."""

    segment_id: str
    known_dimension: str
    value_feet: float


class AreaCalculationSchema(BaseModel):
    """Area calculation row."""

    segment_id: str
    segment_label: str
    region_type: str
    area_sqft: float
    pixel_area: int


class ProjectResponse(BaseModel):
    """Full project detail returned to the client."""

    id: str
    name: str
    status: str
    original_image_url: str = ""
    preprocessed_image_url: Optional[str] = None
    redesigned_image_urls: List[str] = Field(default_factory=list)
    selected_redesign_url: Optional[str] = None
    segments: List[SegmentSchema] = Field(default_factory=list)
    material_selections: List[MaterialSelectionSchema] = Field(default_factory=list)
    reference_measurement: Optional[ReferenceMeasurementSchema] = None
    area_calculations: List[AreaCalculationSchema] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProjectListItem(BaseModel):
    """Compact project card for dashboard."""

    id: str
    name: str
    status: str
    original_image_url: str = ""
    created_at: datetime
    updated_at: datetime


def project_to_response(project: Any) -> ProjectResponse:
    """Map a Project document to ProjectResponse."""
    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        status=project.status,
        original_image_url=project.original_image_url or "",
        preprocessed_image_url=project.preprocessed_image_url,
        redesigned_image_urls=project.redesigned_image_urls or [],
        selected_redesign_url=project.selected_redesign_url,
        segments=[SegmentSchema(**s.model_dump()) for s in (project.segments or [])],
        material_selections=[
            MaterialSelectionSchema(**m.model_dump())
            for m in (project.material_selections or [])
        ],
        reference_measurement=(
            ReferenceMeasurementSchema(**project.reference_measurement.model_dump())
            if project.reference_measurement
            else None
        ),
        area_calculations=[
            AreaCalculationSchema(**a.model_dump())
            for a in (project.area_calculations or [])
        ],
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def project_to_list_item(project: Any) -> ProjectListItem:
    """Map a Project document to a list card."""
    return ProjectListItem(
        id=str(project.id),
        name=project.name,
        status=project.status,
        original_image_url=project.original_image_url or "",
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
