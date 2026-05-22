import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

INDEX_REQUESTED_EVENT_TYPE = "conversation.index_requested.v1"


class ConversationIndexPublisher:
    async def publish_index_requested(self, conversation_id: str, owner_id: str, reason: str) -> bool:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


class NoopConversationIndexPublisher(ConversationIndexPublisher):
    async def publish_index_requested(self, conversation_id: str, owner_id: str, reason: str) -> bool:
        return False


class KafkaConversationIndexPublisher(ConversationIndexPublisher):
    def __init__(self, bootstrap_servers: str, topic: str):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self._producer: Any | None = None

    async def _get_producer(self) -> Any:
        from aiokafka import AIOKafkaProducer

        if self._producer is None:
            producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda value: json.dumps(value, separators=(",", ":")).encode("utf-8"),
                key_serializer=lambda value: value.encode("utf-8"),
            )
            await producer.start()
            self._producer = producer
        return self._producer

    async def publish_index_requested(self, conversation_id: str, owner_id: str, reason: str) -> bool:
        event = {
            "event_id": str(uuid4()),
            "event_type": INDEX_REQUESTED_EVENT_TYPE,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "owner_id": owner_id,
            "conversation_id": conversation_id,
            "reason": reason,
        }
        producer = await self._get_producer()
        await producer.send_and_wait(self.topic, event, key=conversation_id)
        logger.info("published conversation index event. conversation_id=%s reason=%s", conversation_id, reason)
        return True

    async def aclose(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
