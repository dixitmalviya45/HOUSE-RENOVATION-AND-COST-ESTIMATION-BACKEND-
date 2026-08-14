"""
FastAPI application entrypoint for E2M.

Phase 1: auth, health, CORS, DB init, stub routers for later phases.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    estimation,
    materials,
    projects,
    redesign,
    report,
    segmentation,
    upload,
)
from app.config import get_settings
from app.database import init_db


async def _seed_materials_if_empty() -> None:
    """Insert catalog materials once when the collection is empty."""
    try:
        import importlib.util
        from pathlib import Path

        from app.models.material import Material

        seed_path = Path(__file__).resolve().parent.parent / "seed_materials.py"
        spec = importlib.util.spec_from_file_location("seed_materials", seed_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        materials = getattr(module, "MATERIALS", [])

        count = await Material.find_all().count()
        if count == 0 and materials:
            for item in materials:
                await Material(texture_image_url="", **item).insert()
    except Exception:
        # Seeding is best-effort; app should still boot
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize database on startup and seed materials if needed."""
    await init_db()
    await _seed_materials_if_empty()
    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    application = FastAPI(
        title="E2M API",
        description="AI-Based Exterior House Renovation & Cost Estimation System",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_prefix = "/api"
    application.include_router(auth.router, prefix=api_prefix)
    application.include_router(projects.router, prefix=api_prefix)
    application.include_router(upload.router, prefix=api_prefix)
    application.include_router(segmentation.router, prefix=api_prefix)
    application.include_router(materials.router, prefix=api_prefix)
    application.include_router(redesign.router, prefix=api_prefix)
    application.include_router(estimation.router, prefix=api_prefix)
    application.include_router(report.router, prefix=api_prefix)

    @application.get("/health")
    async def health():
        """Liveness probe for Render / local checks."""
        return {"status": "ok", "service": "e2m", "env": settings.app_env}

    return application


app = create_app()
