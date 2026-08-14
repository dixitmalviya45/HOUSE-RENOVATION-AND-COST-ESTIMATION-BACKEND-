"""Material Beanie document — Phase 4 seed catalog."""

from typing import List, Optional

from beanie import Document


class Material(Document):
    """Construction material with INR rates and applicability."""

    name: str
    category: str  # paint | tiles | cladding | railing | texture | panels
    applicable_to: List[str]
    texture_image_url: str = ""
    rate_per_sqft: float
    coverage_per_unit: float = 1.0
    wastage_percent: float = 5.0
    labor_rate_per_sqft: float
    durability: str = "medium"  # high | medium | low
    maintenance: str = "medium"  # high | medium | low
    description: Optional[str] = None

    class Settings:
        name = "materials"
