from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from qdrant_client import AsyncQdrantClient

from app.api.v1.router import router as v1_router
from app.core.config import settings


# lifespan: 앱 시작/종료 시점에 실행할 코드를 정의하는 컨텍스트 매니저
# yield 이전 → 앱 시작 시 실행 (DB 연결 생성)
# yield 이후 → 앱 종료 시 실행 (DB 연결 해제)
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

# CORS: 브라우저는 기본적으로 다른 출처(포트 포함)의 API 호출을 차단함
# 프론트엔드(3003)에서 백엔드(8001)를 호출할 수 있도록 명시적으로 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /api/v1 접두사로 v1 라우터를 앱에 등록
app.include_router(v1_router, prefix="/api/v1")
