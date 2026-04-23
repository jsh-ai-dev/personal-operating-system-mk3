from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from qdrant_client import AsyncQdrantClient

from app.core.config import settings


def get_db(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.mongo[settings.mongodb_db]


def get_qdrant(request: Request) -> AsyncQdrantClient:
    return request.app.state.qdrant
