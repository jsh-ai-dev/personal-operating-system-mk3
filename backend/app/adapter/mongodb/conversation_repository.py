# [저장소] 대화(Conversation)와 메시지(Message)의 MongoDB CRUD 담당
# Clean Architecture 어댑터 레이어 — 도메인 모델과 MongoDB 문서(dict) 간 변환 책임

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.conversation import Conversation, Message


class ConversationRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.conversations = db["conversations"]
        self.messages = db["messages"]

    def _to_conversation(self, doc: dict) -> Conversation:
        def iso(v):
            return v.isoformat() if isinstance(v, datetime) else v

        return Conversation(
            id=str(doc["_id"]),
            provider=doc["provider"],
            model=doc["model"],
            title=doc["title"],
            created_at=iso(doc["created_at"]),
            updated_at=iso(doc["updated_at"]),
            message_count=doc.get("message_count", 0),
            total_tokens_input=doc.get("total_tokens_input", 0),
            total_tokens_output=doc.get("total_tokens_output", 0),
            total_cost_usd=doc.get("total_cost_usd", 0.0),
            summary=doc.get("summary"),
            tags=doc.get("tags", []),
            qdrant_id=doc.get("qdrant_id"),
            source_id=doc.get("source_id"),
            is_hidden=doc.get("is_hidden", False),
        )

    def _to_message(self, doc: dict) -> Message:
        def iso(v):
            return v.isoformat() if isinstance(v, datetime) else v

        return Message(
            id=str(doc["_id"]),
            conversation_id=str(doc["conversation_id"]),
            role=doc["role"],
            content=doc["content"],
            model=doc.get("model"),
            tokens_input=doc.get("tokens_input"),
            tokens_output=doc.get("tokens_output"),
            cost_usd=doc.get("cost_usd"),
            created_at=iso(doc["created_at"]),
            qdrant_id=doc.get("qdrant_id"),
            is_hidden=doc.get("is_hidden", False),
        )

    async def find_all_conversations(self, include_hidden: bool = False) -> list[Conversation]:
        # is_hidden이 True인 문서는 기본적으로 제외 (없는 필드도 False로 처리)
        query = {} if include_hidden else {"is_hidden": {"$ne": True}}
        docs = await self.conversations.find(query).sort("updated_at", -1).to_list(None)
        return [self._to_conversation(doc) for doc in docs]

    async def set_hidden(self, id: str, is_hidden: bool) -> None:
        try:
            await self.conversations.update_one(
                {"_id": ObjectId(id)},
                {"$set": {"is_hidden": is_hidden, "updated_at": datetime.now(timezone.utc)}},
            )
        except InvalidId:
            pass

    async def find_conversation_by_id(self, id: str) -> Conversation | None:
        try:
            doc = await self.conversations.find_one({"_id": ObjectId(id)})
        except InvalidId:
            return None
        return self._to_conversation(doc) if doc else None

    async def create_conversation(
        self, provider: str, model: str, title: str, source_id: str | None = None
    ) -> Conversation:
        now = datetime.now(timezone.utc)
        result = await self.conversations.insert_one({
            "provider": provider,
            "model": model,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
            "total_tokens_input": 0,
            "total_tokens_output": 0,
            "total_cost_usd": 0.0,
            "summary": None,
            "tags": [],
            "qdrant_id": None,
            "source_id": source_id,
        })
        return await self.find_conversation_by_id(str(result.inserted_id))

    async def find_conversation_by_source_id(self, source_id: str) -> Conversation | None:
        doc = await self.conversations.find_one({"source_id": source_id})
        return self._to_conversation(doc) if doc else None

    async def set_message_hidden(self, message_id: str, is_hidden: bool) -> None:
        try:
            await self.messages.update_one(
                {"_id": ObjectId(message_id)},
                {"$set": {"is_hidden": is_hidden}},
            )
        except InvalidId:
            pass

    async def update_message_content(self, message_id: str, content: str) -> None:
        try:
            await self.messages.update_one(
                {"_id": ObjectId(message_id)},
                {"$set": {"content": content}},
            )
        except InvalidId:
            pass

    async def set_message_count(self, id: str, count: int) -> None:
        try:
            await self.conversations.update_one(
                {"_id": ObjectId(id)},
                {"$set": {"message_count": count, "updated_at": datetime.now(timezone.utc)}},
            )
        except InvalidId:
            pass

    async def update_conversation_stats(
        self, id: str, tokens_input: int, tokens_output: int, cost_usd: float
    ) -> None:
        try:
            await self.conversations.update_one(
                {"_id": ObjectId(id)},
                {
                    "$inc": {
                        "message_count": 2,
                        "total_tokens_input": tokens_input,
                        "total_tokens_output": tokens_output,
                        "total_cost_usd": cost_usd,
                    },
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                },
            )
        except InvalidId:
            pass

    async def find_messages_by_conversation(self, conversation_id: str) -> list[Message]:
        try:
            oid = ObjectId(conversation_id)
        except InvalidId:
            return []
        docs = await self.messages.find({"conversation_id": oid}).sort("created_at", 1).to_list(None)
        return [self._to_message(doc) for doc in docs]

    async def insert_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        model: str | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        cost_usd: float | None = None,
        created_at: datetime | None = None,  # 임포트 시 원본 타임스탬프 보존용
    ) -> Message:
        now = created_at or datetime.now(timezone.utc)
        result = await self.messages.insert_one({
            "conversation_id": ObjectId(conversation_id),
            "role": role,
            "content": content,
            "model": model,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "cost_usd": cost_usd,
            "created_at": now,
            "qdrant_id": None,
        })
        doc = await self.messages.find_one({"_id": result.inserted_id})
        return self._to_message(doc)
