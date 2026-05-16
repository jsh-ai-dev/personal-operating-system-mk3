# [API] B 방식 데이터 임포트 엔드포인트
# /import 접두사로 각 소스별 임포트 트리거를 제공
# 임포트 완료 직후 Qdrant 임베딩까지 처리하여 즉시 의미 검색 가능

from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
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
from app.core.s3 import S3Client

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

    # s3_bucket이 설정돼 있으면 S3Client 생성 → 없으면 None (로컬 data/ 경로 사용)
    # 액세스 키가 없으면 boto3가 EC2 IAM Role(인스턴스 메타데이터)에서 자동으로 자격증명을 가져옴
    s3 = None
    if settings.s3_bucket:
        s3 = S3Client(
            bucket=settings.s3_bucket,
            region=settings.aws_region,
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
            prefix=settings.s3_prefix,
        )

    return ImportService(ConversationRepository(db), search_svc, s3)


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


@router.post("/chatgpt-export")
async def import_chatgpt_export(
    svc: ImportService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return await svc.import_chatgpt_export(user.id, settings.chatgpt_export_path)


@router.post("/gemini-takeout")
async def import_gemini_takeout(
    svc: ImportService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return await svc.import_gemini_takeout(user.id, settings.gemini_takeout_path)


# 서비스별 S3 키 — 단일 파일은 고정 키, 다중 파일은 파일명 그대로 사용
_S3_UPLOAD_KEY: dict[str, str | None] = {
    "chatgpt-export": "chatgpt/conversations.json",
    "claude-export": "claude/conversations.json",
    "gemini-takeout": "gemini/내활동.json",
    "claude-code": None,      # 다중 파일 → 파일명 그대로 claude-code/{filename}
    "jetbrains-codex": None,  # 다중 파일 → 파일명 그대로 codex/{filename}
}

_S3_UPLOAD_PREFIX: dict[str, str] = {
    "claude-code": "claude-code/",
    "jetbrains-codex": "codex/",
}


@router.get("/history")
async def get_import_history(
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    repo = ConversationRepository(db)
    return await repo.get_import_history(user.id)


@router.post("/upload/{service}")
async def upload_import_files(
    service: Literal["chatgpt-export", "claude-export", "gemini-takeout", "claude-code", "jetbrains-codex"],
    files: list[UploadFile] = File(...),
    user: AuthUser = Depends(get_current_user),
):
    if not settings.s3_bucket:
        raise HTTPException(status_code=400, detail="S3가 설정되지 않았습니다")

    s3 = S3Client(
        bucket=settings.s3_bucket,
        region=settings.aws_region,
        access_key_id=settings.aws_access_key_id,
        secret_access_key=settings.aws_secret_access_key,
        prefix=settings.s3_prefix,
    )

    uploaded = 0
    for file in files:
        content = await file.read()
        fixed_key = _S3_UPLOAD_KEY.get(service)
        if fixed_key:
            key = fixed_key
        else:
            prefix = _S3_UPLOAD_PREFIX[service]
            key = f"{prefix}{file.filename}"

        await s3.upload_file(key, content, file.content_type or "application/octet-stream")
        uploaded += 1

    return {"uploaded": uploaded}
