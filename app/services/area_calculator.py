"""Pixel-to-sqft area calculation."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.models.project import AreaCalculation, ReferenceMeasurement


def calculate_areas(project, reference: ReferenceMeasurement) -> list[AreaCalculation]:
    """
    Scale segment pixel areas using a user reference measurement.

    scale_factor = known_feet / reference_pixels
    area_sqft = pixel_area * (scale_factor ** 2)
    """
    if not project.segments:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No segments available for area calculation",
        )

    ref_segment = next((s for s in project.segments if s.id == reference.segment_id), None)
    if ref_segment is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Reference segment not found",
        )

    if not ref_segment.bbox or len(ref_segment.bbox) < 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Reference segment is missing bounding box data",
        )

    _, _, width_px, height_px = ref_segment.bbox[:4]
    dimension = reference.known_dimension.lower()
    if dimension not in ("height", "width"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="known_dimension must be 'height' or 'width'",
        )
    if reference.value_feet <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Reference value must be greater than zero",
        )

    reference_pixels = height_px if dimension == "height" else width_px
    if reference_pixels <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid reference pixel dimension",
        )

    scale_factor = reference.value_feet / float(reference_pixels)
    results: list[AreaCalculation] = []
    for segment in project.segments:
        pixel_area = segment.pixel_area
        if pixel_area <= 0 and segment.bbox and len(segment.bbox) >= 4:
            pixel_area = int(segment.bbox[2] * segment.bbox[3])
        area_sqft = round(pixel_area * (scale_factor ** 2), 2)
        results.append(
            AreaCalculation(
                segment_id=segment.id,
                segment_label=segment.label,
                region_type=segment.region_type,
                area_sqft=max(area_sqft, 0.01),
                pixel_area=pixel_area,
            )
        )
    return results
