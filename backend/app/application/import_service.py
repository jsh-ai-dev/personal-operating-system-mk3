# [서비스] B 방식 — 외부 소스에서 가져온 대화를 MongoDB에 저장하는 임포트 서비스
# source_id로 중복 감지 → 같은 세션을 두 번 임포트해도 데이터가 쌓이지 않음

from pathlib import Path

from app.adapter.importer.claude_code_importer import scan_sessions as scan_claude_code_sessions
from app.adapter.importer.claude_importer import parse_export as parse_claude_export
from app.adapter.importer.gemini_importer import parse_takeout
from app.adapter.importer.jetbrains_codex_importer import scan_sessions
from app.adapter.mongodb.conversation_repository import ConversationRepository


class ImportService:
    def __init__(self, repo: ConversationRepository):
        self.repo = repo

    async def import_jetbrains_codex(self, aia_path: str) -> dict:
        sessions = scan_sessions(aia_path)
        imported = 0
        skipped = 0

        for session in sessions:
            existing = await self.repo.find_conversation_by_source_id(session.session_id)
            if existing:
                skipped += 1
                continue

            conv = await self.repo.create_conversation(
                provider="jetbrains",
                model="codex",
                title=session.title,
                source_id=session.session_id,
            )

            for msg in session.messages:
                await self.repo.insert_message(
                    conversation_id=conv.id,
                    role=msg["role"],
                    content=msg["content"],
                )

            await self.repo.set_message_count(conv.id, len(session.messages))
            imported += 1

        return {"imported": imported, "skipped": skipped, "total": len(sessions)}

    async def import_claude_code(self, code_path: str) -> dict:
        sessions = scan_claude_code_sessions(code_path)
        imported = 0
        skipped = 0

        for session in sessions:
            existing = await self.repo.find_conversation_by_source_id(session.session_id)
            if existing:
                skipped += 1
                continue

            conv = await self.repo.create_conversation(
                provider="anthropic",
                model="claude-code",
                title=session.title,
                source_id=session.session_id,
            )

            for msg in session.messages:
                await self.repo.insert_message(
                    conversation_id=conv.id,
                    role=msg["role"],
                    content=msg["content"],
                    created_at=msg["created_at"],
                )

            await self.repo.set_message_count(conv.id, len(session.messages))
            imported += 1

        return {"imported": imported, "skipped": skipped, "total": len(sessions)}

    async def import_claude_export(self, export_path: str) -> dict:
        sessions = parse_claude_export(Path(export_path))
        imported = 0
        skipped = 0

        for session in sessions:
            existing = await self.repo.find_conversation_by_source_id(session.session_id)
            if existing:
                skipped += 1
                continue

            conv = await self.repo.create_conversation(
                provider="anthropic",
                model="claude",
                title=session.title,
                source_id=session.session_id,
            )

            for msg in session.messages:
                await self.repo.insert_message(
                    conversation_id=conv.id,
                    role=msg["role"],
                    content=msg["content"],
                    created_at=msg["created_at"],
                )

            await self.repo.set_message_count(conv.id, len(session.messages))
            imported += 1

        return {"imported": imported, "skipped": skipped, "total": len(sessions)}

    async def import_gemini_takeout(self, takeout_path: str) -> dict:
        sessions = parse_takeout(Path(takeout_path))
        imported = 0
        skipped = 0

        for session in sessions:
            existing = await self.repo.find_conversation_by_source_id(session.session_id)
            if existing:
                skipped += 1
                continue

            conv = await self.repo.create_conversation(
                provider="google",
                model="gemini",
                title=session.title,
                source_id=session.session_id,
            )

            for msg in session.messages:
                await self.repo.insert_message(
                    conversation_id=conv.id,
                    role=msg["role"],
                    content=msg["content"],
                    created_at=msg["created_at"],
                )

            await self.repo.set_message_count(conv.id, len(session.messages))
            imported += 1

        return {"imported": imported, "skipped": skipped, "total": len(sessions)}
