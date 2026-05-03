# [API] 의미 검색 엔드포인트 — 질의어를 임베딩해서 유사한 대화를 찾아 반환
# GET /search?q=... 로 검색, POST /search/index 로 기존 대화 전체 인덱싱

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.adapter.mongodb.conversation_repository import ConversationRepository
from app.adapter.qdrant.vector_repository import VectorRepository
from app.application.search_service import SearchService
from app.core.auth import AuthUser, get_current_user
from app.core.config import settings
from app.core.dependencies import get_db, get_qdrant

router = APIRouter(prefix="/search", tags=["search"])


def _get_svc(
    db: AsyncIOMotorDatabase = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
) -> SearchService:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    return SearchService(ConversationRepository(db), VectorRepository(qdrant), client)


def _require_openai() -> None:
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY가 설정되지 않았습니다")


@router.get("")
async def search_conversations(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    svc: SearchService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    _require_openai()
    return await svc.search(q, user.id, limit)


@router.post("/index")
async def index_all_conversations(
    svc: SearchService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    # 최초 1회 또는 임베딩 누락 시 전체 재인덱싱 — 완료까지 몇 분 걸릴 수 있음
    _require_openai()
    return await svc.index_all(user.id)
