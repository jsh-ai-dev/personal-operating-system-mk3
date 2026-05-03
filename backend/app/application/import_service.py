# [서비스] B 방식 — 외부 소스에서 가져온 대화를 MongoDB에 저장하는 임포트 서비스
# source_id로 중복 감지 → 같은 세션을 두 번 임포트해도 데이터가 쌓이지 않음
# 임포트 직후 SearchService를 통해 Qdrant에 임베딩 → 즉시 의미 검색 가능

import logging
from pathlib import Path

from app.adapter.importer.claude_code_importer import scan_sessions as scan_claude_code_sessions
from app.adapter.importer.claude_importer import parse_export as parse_claude_export
from app.adapter.importer.gemini_importer import parse_takeout
from app.adapter.importer.jetbrains_codex_importer import scan_sessions
from app.adapter.mongodb.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)


class ImportService:
    def __init__(self, repo: ConversationRepository, search_svc=None):
        self.repo = repo
        # search_svc는 선택적 의존성 — OpenAI 키가 없는 환경에서도 임포트는 동작해야 함
        self.search_svc = search_svc

    async def _try_embed(self, conversation_id: str, owner_id: str) -> None:
        if not self.search_svc:
            return
        try:
            await self.search_svc.embed_conversation(conversation_id, owner_id)
        except Exception as e:
            # 임베딩 실패가 임포트 전체를 막으면 안 됨 — 나중에 /search/index로 재시도 가능
            logger.warning("embed failed for %s: %s", conversation_id, e)

    async def import_jetbrains_codex(self, owner_id: str, aia_path: str) -> dict:
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

        return {"imported": imported, "skipped": skipped, "total": len(sessions)}

    async def import_claude_code(self, owner_id: str, code_path: str) -> dict:
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

        return {"imported": imported, "skipped": skipped, "total": len(sessions)}

    async def import_claude_export(self, owner_id: str, export_path: str) -> dict:
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

        return {"imported": imported, "skipped": skipped, "total": len(sessions)}

    async def import_gemini_takeout(self, owner_id: str, takeout_path: str) -> dict:
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

        return {"imported": imported, "skipped": skipped, "total": len(sessions)}
