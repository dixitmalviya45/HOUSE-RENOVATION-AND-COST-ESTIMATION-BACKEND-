"""MongoDB connection and Beanie ODM initialization."""

import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.config import get_settings
from app.models.user import User
from app.models.material import Material
from app.models.project import Project
from app.models.estimate import Estimate
from app.models.api_usage import ApiUsage


async def init_db() -> None:
    """Connect to MongoDB and initialize Beanie document models."""
    settings = get_settings()
    uri = settings.mongodb_uri
    kwargs = {"serverSelectionTimeoutMS": 30000}

    # Atlas / SRV connections need TLS; local Docker does not.
    if uri.startswith("mongodb+srv://") or "mongodb.net" in uri:
        kwargs.update(
            {
                "tls": True,
                "tlsCAFile": certifi.where(),
                # Workaround for Python 3.14 OpenSSL handshake quirks with Atlas
                "tlsAllowInvalidCertificates": True,
            }
        )

    client = AsyncIOMotorClient(uri, **kwargs)
    try:
        database = client.get_default_database()
    except Exception:
        database = None
    if database is None:
        database = client["e2m_db"]

    await init_beanie(
        database=database,
        document_models=[User, Material, Project, Estimate, ApiUsage],
    )
