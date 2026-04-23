from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from qdrant_client import AsyncQdrantClient

from app.core.dependencies import get_db, get_qdrant

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    db: AsyncIOMotorDatabase = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
):
    await db.command("ping")
    await qdrant.get_collections()
    return {"status": "ok", "mongodb": "ok", "qdrant": "ok"}
