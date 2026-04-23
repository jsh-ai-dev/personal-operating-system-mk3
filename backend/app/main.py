from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from qdrant_client import AsyncQdrantClient

from app.api.v1.router import router as v1_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mongo = AsyncIOMotorClient(settings.mongodb_url)
    app.state.qdrant = AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
    )
    yield
    app.state.mongo.close()
    await app.state.qdrant.close()


app = FastAPI(title="Personal Operating System mk3", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")
