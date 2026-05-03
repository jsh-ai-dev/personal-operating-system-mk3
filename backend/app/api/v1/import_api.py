# [API] B 방식 데이터 임포트 엔드포인트
# /import 접두사로 각 소스별 임포트 트리거를 제공
# 임포트 완료 직후 Qdrant 임베딩까지 처리하여 즉시 의미 검색 가능

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.adapter.mongodb.conversation_repository import ConversationRepository
from app.adapter.qdrant.vector_repository import VectorRepository
from app.application.import_service import ImportService
from app.application.search_service import SearchService
from app.core.auth import AuthUser, get_current_user
from app.core.config import settings
from app.core.dependencies import get_db, get_qdrant

router = APIRouter(prefix="/import", tags=["import"])


def _get_svc(
    db: AsyncIOMotorDatabase = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
) -> ImportService:
    # OpenAI 키가 없으면 search_svc=None → 임베딩 없이 임포트만 진행
    search_svc = None
    if settings.openai_api_key:
        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        search_svc = SearchService(ConversationRepository(db), VectorRepository(qdrant), openai_client)
    return ImportService(ConversationRepository(db), search_svc)


@router.post("/jetbrains-codex")
async def import_jetbrains_codex(
    svc: ImportService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return await svc.import_jetbrains_codex(user.id, settings.jetbrains_aia_path)


@router.post("/claude-code")
async def import_claude_code(
    svc: ImportService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return await svc.import_claude_code(user.id, settings.claude_code_path)


@router.post("/claude-export")
async def import_claude_export(
    svc: ImportService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return await svc.import_claude_export(user.id, settings.claude_export_path)


@router.post("/gemini-takeout")
async def import_gemini_takeout(
    svc: ImportService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return await svc.import_gemini_takeout(user.id, settings.gemini_takeout_path)
