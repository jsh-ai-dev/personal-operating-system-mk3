# [서비스] B 방식 — 외부 소스에서 가져온 대화를 MongoDB에 저장하는 임포트 서비스
# source_id로 중복 감지 → 같은 세션을 두 번 임포트해도 데이터가 쌓이지 않음

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
