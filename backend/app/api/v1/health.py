# [헬스체크 API] GET /api/v1/health — MongoDB와 Qdrant 연결 상태를 확인하는 엔드포인트
# 서버가 정상적으로 동작 중인지 빠르게 확인할 때 사용

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from qdrant_client import AsyncQdrantClient

from app.core.dependencies import get_db, get_qdrant

router = APIRouter(tags=["health"])


# GET /api/v1/health — MongoDB와 Qdrant가 모두 정상인지 확인
# Depends()로 DB 클라이언트를 주입받음 (직접 생성하지 않음)
@router.get("/health")
async def health(
    db: AsyncIOMotorDatabase = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
):
    await db.command("ping")        # MongoDB 응답 여부 확인
    await qdrant.get_collections()  # Qdrant 응답 여부 확인
    return {"status": "ok", "mongodb": "ok", "qdrant": "ok"}
