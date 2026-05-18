# [서비스] B 방식 — 외부 소스에서 가져온 대화를 MongoDB에 저장하는 임포트 서비스
# source_id로 중복 감지 → 같은 세션을 두 번 임포트해도 데이터가 쌓이지 않음
# 임포트 직후 SearchService를 통해 Qdrant에 임베딩 → 즉시 의미 검색 가능
# S3 설정 시: 로컬 data/ 경로 대신 S3에서 파일을 임시 디렉토리에 받아 처리

import logging
import shutil
import tempfile
from pathlib import Path
from urllib.parse import quote

from app.adapter.importer.chatgpt_importer import parse_export as parse_chatgpt_export
from app.adapter.importer.claude_code_importer import scan_sessions as scan_claude_code_sessions
from app.adapter.importer.claude_importer import parse_export as parse_claude_export
from app.adapter.importer.gemini_importer import parse_takeout
from app.adapter.importer.jetbrains_codex_importer import scan_sessions
from app.adapter.mongodb.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)

# S3 버킷 내 폴더 구조 — 로컬 data/ 구조와 동일하게 유지
_S3_CHATGPT_KEY = "chatgpt/conversations.json"
_S3_CLAUDE_KEY = "claude/conversations.json"
_S3_GEMINI_KEY = "gemini/내활동.json"
_S3_CLAUDE_CODE_PREFIX = "claude-code/"
_S3_CODEX_PREFIX = "codex/"


class ImportUploadRequired(Exception):
    pass


class ImportUploadNotFound(Exception):
    pass


class ImportService:
    def __init__(self, repo: ConversationRepository, search_svc=None, s3=None):
        self.repo = repo
        self.search_svc = search_svc
        # search_svc는 선택적 의존성 — OpenAI 키가 없는 환경에서도 임포트는 동작해야 함
        self.search_svc = search_svc
        # s3는 선택적 의존성 — None이면 로컬 data/ 경로에서 읽음
        self.s3 = s3

    def _s3_key(self, owner_id: str, upload_id: str, key: str) -> str:
        return f"imports/{quote(owner_id, safe='')}/{upload_id}/{key}"

    async def _resolve_upload_id(self, owner_id: str, service: str, upload_id: str | None) -> str:
        if not upload_id:
            raise ImportUploadRequired("S3 import requires a selected upload_id.")
        upload = await self.repo.find_import_upload(owner_id, service, upload_id)
        if not upload:
            raise ImportUploadNotFound("Import upload was not found for this user and service.")
        return upload["upload_id"]

    async def _mark_upload_imported(self, owner_id: str, service: str, upload_id: str | None) -> None:
        if upload_id:
            await self.repo.mark_import_upload_imported(owner_id, service, upload_id)

    async def _try_embed(self, conversation_id: str, owner_id: str) -> None:
        if not self.search_svc:
            return
        try:
            await self.search_svc.embed_conversation(conversation_id, owner_id)
        except Exception as e:
            # 임베딩 실패가 임포트 전체를 막으면 안 됨 — 나중에 /search/index로 재시도 가능
            logger.warning("embed failed for %s: %s", conversation_id, e)

    async def _s3_download_file(self, s3_key: str) -> tuple[Path, Path]:
        """S3에서 파일 하나를 임시 디렉토리에 다운로드. 반환값: (tmp_dir, 파일경로). 호출자가 cleanup 책임."""
        tmp_dir = Path(tempfile.mkdtemp())
        dest = tmp_dir / Path(s3_key).name
        await self.s3.download_file(s3_key, dest)
        return tmp_dir, dest

    async def _s3_download_prefix(self, prefix: str) -> Path:
        """S3 prefix 하위 파일 전체를 임시 디렉토리에 다운로드. 반환값: tmp_dir. 호출자가 cleanup 책임."""
        tmp_dir = Path(tempfile.mkdtemp())
        keys = await self.s3.list_keys(prefix)
        for key in keys:
            await self.s3.download_file(key, tmp_dir / Path(key).name)
        return tmp_dir

    async def import_jetbrains_codex(self, owner_id: str, aia_path: str, upload_id: str | None = None) -> dict:
        if self.s3:
            upload_id = await self._resolve_upload_id(owner_id, "jetbrains-codex", upload_id)
            tmp_dir = await self._s3_download_prefix(self._s3_key(owner_id, upload_id, _S3_CODEX_PREFIX))
            try:
                sessions = scan_sessions(str(tmp_dir))
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
        else:
            sessions = scan_sessions(aia_path)

        imported = 0
        skipped = 0

        for session in sessions:
            existing = await self.repo.find_conversation_by_source_id(session.session_id, owner_id)
            if existing:
                skipped += 1
                continue

            conv = await self.repo.create_conversation(
                provider="jetbrains",
                model="codex",
                title=session.title,
                owner_id=owner_id,
                source_id=session.session_id,
                created_at=session.created_at,
            )

            for msg in session.messages:
                await self.repo.insert_message(
                    conversation_id=conv.id,
                    owner_id=owner_id,
                    role=msg["role"],
                    content=msg["content"],
                )

            await self.repo.set_message_count(conv.id, owner_id, len(session.messages))
            await self._try_embed(conv.id, owner_id)
            imported += 1

        if imported > 0:
            await self.repo.upsert_import_history("jetbrains-codex", owner_id, imported)
        await self._mark_upload_imported(owner_id, "jetbrains-codex", upload_id)
        return {"imported": imported, "skipped": skipped, "total": len(sessions)}

    async def import_claude_code(self, owner_id: str, code_path: str, upload_id: str | None = None) -> dict:
        if self.s3:
            upload_id = await self._resolve_upload_id(owner_id, "claude-code", upload_id)
            tmp_dir = await self._s3_download_prefix(self._s3_key(owner_id, upload_id, _S3_CLAUDE_CODE_PREFIX))
            try:
                sessions = scan_claude_code_sessions(str(tmp_dir))
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
        else:
            sessions = scan_claude_code_sessions(code_path)

        imported = 0
        skipped = 0

        for session in sessions:
            existing = await self.repo.find_conversation_by_source_id(session.session_id, owner_id)
            if existing:
                skipped += 1
                continue

            conv = await self.repo.create_conversation(
                provider="anthropic",
                model="claude-code",
                title=session.title,
                owner_id=owner_id,
                source_id=session.session_id,
                created_at=session.messages[0]["created_at"] if session.messages else None,
            )

            for msg in session.messages:
                await self.repo.insert_message(
                    conversation_id=conv.id,
                    owner_id=owner_id,
                    role=msg["role"],
                    content=msg["content"],
                    created_at=msg["created_at"],
                )

            await self.repo.set_message_count(conv.id, owner_id, len(session.messages))
            await self._try_embed(conv.id, owner_id)
            imported += 1

        if imported > 0:
            await self.repo.upsert_import_history("claude-code", owner_id, imported)
        await self._mark_upload_imported(owner_id, "claude-code", upload_id)
        return {"imported": imported, "skipped": skipped, "total": len(sessions)}

    async def import_claude_export(self, owner_id: str, export_path: str, upload_id: str | None = None) -> dict:
        if self.s3:
            upload_id = await self._resolve_upload_id(owner_id, "claude-export", upload_id)
            tmp_dir, tmp_file = await self._s3_download_file(self._s3_key(owner_id, upload_id, _S3_CLAUDE_KEY))
            try:
                sessions = parse_claude_export(tmp_file)
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
        else:
            sessions = parse_claude_export(Path(export_path))

        imported = 0
        skipped = 0

        for session in sessions:
            existing = await self.repo.find_conversation_by_source_id(session.session_id, owner_id)
            if existing:
                skipped += 1
                continue

            conv = await self.repo.create_conversation(
                provider="anthropic",
                model="claude",
                title=session.title,
                owner_id=owner_id,
                source_id=session.session_id,
                created_at=session.messages[0]["created_at"] if session.messages else None,
            )

            for msg in session.messages:
                await self.repo.insert_message(
                    conversation_id=conv.id,
                    owner_id=owner_id,
                    role=msg["role"],
                    content=msg["content"],
                    created_at=msg["created_at"],
                )

            await self.repo.set_message_count(conv.id, owner_id, len(session.messages))
            await self._try_embed(conv.id, owner_id)
            imported += 1

        if imported > 0:
            await self.repo.upsert_import_history("claude-export", owner_id, imported)
        await self._mark_upload_imported(owner_id, "claude-export", upload_id)
        return {"imported": imported, "skipped": skipped, "total": len(sessions)}

    async def import_chatgpt_export(self, owner_id: str, export_path: str, upload_id: str | None = None) -> dict:
        if self.s3:
            upload_id = await self._resolve_upload_id(owner_id, "chatgpt-export", upload_id)
            tmp_dir, tmp_file = await self._s3_download_file(self._s3_key(owner_id, upload_id, _S3_CHATGPT_KEY))
            try:
                sessions = parse_chatgpt_export(tmp_file)
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
        else:
            sessions = parse_chatgpt_export(Path(export_path))

        imported = 0
        skipped = 0

        for session in sessions:
            existing = await self.repo.find_conversation_by_source_id(session.session_id, owner_id)
            if existing:
                skipped += 1
                continue

            conv = await self.repo.create_conversation(
                provider="openai",
                model="chatgpt",
                title=session.title,
                owner_id=owner_id,
                source_id=session.session_id,
                created_at=session.messages[0]["created_at"] if session.messages else None,
            )

            for msg in session.messages:
                await self.repo.insert_message(
                    conversation_id=conv.id,
                    owner_id=owner_id,
                    role=msg["role"],
                    content=msg["content"],
                    created_at=msg["created_at"],
                )

            await self.repo.set_message_count(conv.id, owner_id, len(session.messages))
            await self._try_embed(conv.id, owner_id)
            imported += 1

        if imported > 0:
            await self.repo.upsert_import_history("chatgpt-export", owner_id, imported)
        await self._mark_upload_imported(owner_id, "chatgpt-export", upload_id)
        return {"imported": imported, "skipped": skipped, "total": len(sessions)}

    async def import_gemini_takeout(self, owner_id: str, takeout_path: str, upload_id: str | None = None) -> dict:
        if self.s3:
            upload_id = await self._resolve_upload_id(owner_id, "gemini-takeout", upload_id)
            tmp_dir, tmp_file = await self._s3_download_file(self._s3_key(owner_id, upload_id, _S3_GEMINI_KEY))
            try:
                sessions = parse_takeout(tmp_file)
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
        else:
            sessions = parse_takeout(Path(takeout_path))

        imported = 0
        skipped = 0

        for session in sessions:
            existing = await self.repo.find_conversation_by_source_id(session.session_id, owner_id)
            if existing:
                skipped += 1
                continue

            conv = await self.repo.create_conversation(
                provider="google",
                model="gemini",
                title=session.title,
                owner_id=owner_id,
                source_id=session.session_id,
                created_at=session.messages[0]["created_at"] if session.messages else None,
            )

            for msg in session.messages:
                await self.repo.insert_message(
                    conversation_id=conv.id,
                    owner_id=owner_id,
                    role=msg["role"],
                    content=msg["content"],
                    created_at=msg["created_at"],
                )

            await self.repo.set_message_count(conv.id, owner_id, len(session.messages))
            await self._try_embed(conv.id, owner_id)
            imported += 1

        if imported > 0:
            await self.repo.upsert_import_history("gemini-takeout", owner_id, imported)
        await self._mark_upload_imported(owner_id, "gemini-takeout", upload_id)
        return {"imported": imported, "skipped": skipped, "total": len(sessions)}
