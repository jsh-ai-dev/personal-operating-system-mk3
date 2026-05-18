# [API] B 방식 데이터 임포트 엔드포인트
# /import 접두사로 각 소스별 임포트 트리거를 제공
# 임포트 완료 직후 Qdrant 임베딩까지 처리하여 즉시 의미 검색 가능

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase
from openai import AsyncOpenAI
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from app.adapter.mongodb.conversation_repository import ConversationRepository
from app.adapter.qdrant.vector_repository import VectorRepository
from app.application.import_service import ImportService, ImportUploadNotFound, ImportUploadRequired
from app.application.search_service import SearchService
from app.core.auth import AuthUser, get_current_user
from app.core.config import settings
from app.core.dependencies import get_db, get_qdrant
from app.core.s3 import S3Client

router = APIRouter(prefix="/import", tags=["import"])

ImportServiceName = Literal["chatgpt-export", "claude-export", "gemini-takeout", "claude-code", "jetbrains-codex"]


class ImportRequest(BaseModel):
    upload_id: str | None = None


def _iso(v):
    if isinstance(v, datetime):
        return v.replace(tzinfo=timezone.utc).isoformat() if v.tzinfo is None else v.isoformat()
    return v


def _upload_response(doc: dict) -> dict:
    filenames = doc.get("original_filenames") or [Path(key).name for key in doc.get("file_keys", [])]
    return {
        "upload_id": doc["upload_id"],
        "service": doc["service"],
        "filenames": filenames,
        "file_count": doc.get("file_count", len(doc.get("file_keys", []))),
        "created_at": _iso(doc.get("created_at")),
        "imported_at": _iso(doc.get("imported_at")),
    }


async def _run_import(coro):
    try:
        return await coro
    except ImportUploadRequired as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ImportUploadNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


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
    request: ImportRequest | None = None,
    svc: ImportService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return await _run_import(
        svc.import_jetbrains_codex(user.id, settings.jetbrains_aia_path, request.upload_id if request else None)
    )


@router.post("/claude-code")
async def import_claude_code(
    request: ImportRequest | None = None,
    svc: ImportService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return await _run_import(
        svc.import_claude_code(user.id, settings.claude_code_path, request.upload_id if request else None)
    )


@router.post("/claude-export")
async def import_claude_export(
    request: ImportRequest | None = None,
    svc: ImportService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return await _run_import(
        svc.import_claude_export(user.id, settings.claude_export_path, request.upload_id if request else None)
    )


@router.post("/chatgpt-export")
async def import_chatgpt_export(
    request: ImportRequest | None = None,
    svc: ImportService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return await _run_import(
        svc.import_chatgpt_export(user.id, settings.chatgpt_export_path, request.upload_id if request else None)
    )


@router.post("/gemini-takeout")
async def import_gemini_takeout(
    request: ImportRequest | None = None,
    svc: ImportService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return await _run_import(
        svc.import_gemini_takeout(user.id, settings.gemini_takeout_path, request.upload_id if request else None)
    )


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


@router.get("/uploads/{service}")
async def list_import_uploads(
    service: ImportServiceName,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    repo = ConversationRepository(db)
    docs = await repo.list_import_uploads(user.id, service)
    return [_upload_response(doc) for doc in docs]


@router.delete("/uploads/{service}/{upload_id}")
async def delete_import_upload(
    service: ImportServiceName,
    upload_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    if not settings.s3_bucket:
        raise HTTPException(status_code=400, detail="S3 is not configured.")

    repo = ConversationRepository(db)
    upload = await repo.find_import_upload(user.id, service, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Import upload was not found for this user and service.")

    s3 = S3Client(
        bucket=settings.s3_bucket,
        region=settings.aws_region,
        access_key_id=settings.aws_access_key_id,
        secret_access_key=settings.aws_secret_access_key,
        prefix=settings.s3_prefix,
    )
    await s3.delete_files(upload.get("file_keys", []))
    await repo.delete_import_upload(user.id, service, upload_id)
    return {"deleted": True}


@router.post("/upload/{service}")
async def upload_import_files(
    service: ImportServiceName,
    files: list[UploadFile] = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    if not settings.s3_bucket:
        raise HTTPException(status_code=400, detail="S3가 설정되지 않았습니다")

    if _S3_UPLOAD_KEY.get(service) and len(files) != 1:
        raise HTTPException(status_code=400, detail="This import type requires exactly one file.")

    s3 = S3Client(
        bucket=settings.s3_bucket,
        region=settings.aws_region,
        access_key_id=settings.aws_access_key_id,
        secret_access_key=settings.aws_secret_access_key,
        prefix=settings.s3_prefix,
    )

    upload_id = uuid4().hex
    upload_prefix = f"imports/{quote(user.id, safe='')}/{upload_id}/"
    file_keys: list[str] = []
    original_filenames: list[str] = []
    uploaded = 0
    for file in files:
        content = await file.read()
        original_filename = Path(file.filename or "").name
        fixed_key = _S3_UPLOAD_KEY.get(service)
        if fixed_key:
            key = f"{upload_prefix}{fixed_key}"
            original_filenames.append(original_filename or Path(fixed_key).name)
        else:
            prefix = _S3_UPLOAD_PREFIX[service]
            if not original_filename:
                raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")
            key = f"{upload_prefix}{prefix}{original_filename}"
            original_filenames.append(original_filename)

        await s3.upload_file(key, content, file.content_type or "application/octet-stream")
        file_keys.append(key)
        uploaded += 1

    repo = ConversationRepository(db)
    await repo.create_import_upload(user.id, service, upload_id, upload_prefix, file_keys, original_filenames)

    return {"uploaded": uploaded, "upload_id": upload_id}
