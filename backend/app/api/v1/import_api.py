# [API] B 방식 데이터 임포트 엔드포인트
# /import 접두사로 각 소스별 임포트 트리거를 제공

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.adapter.mongodb.conversation_repository import ConversationRepository
from app.application.import_service import ImportService
from app.core.config import settings
from app.core.dependencies import get_db

router = APIRouter(prefix="/import", tags=["import"])


def _get_svc(db: AsyncIOMotorDatabase = Depends(get_db)) -> ImportService:
    return ImportService(ConversationRepository(db))


@router.post("/jetbrains-codex")
async def import_jetbrains_codex(svc: ImportService = Depends(_get_svc)):
    return await svc.import_jetbrains_codex(settings.jetbrains_aia_path)
