import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from motor.motor_asyncio import AsyncIOMotorClient
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.adapter.mongodb.conversation_repository import ConversationRepository
from app.adapter.qdrant.vector_repository import VectorRepository
from app.application.conversation_index_events import INDEX_REQUESTED_EVENT_TYPE
from app.application.search_service import SearchService
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logging.getLogger("aiokafka").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def _handle_event(event: dict, search_svc: SearchService) -> None:
    event_type = event.get("event_type")
    conversation_id = event.get("conversation_id")
    owner_id = event.get("owner_id")

    if event_type != INDEX_REQUESTED_EVENT_TYPE:
        logger.warning("skip unsupported event type: %s", event_type)
        return
    if not conversation_id or not owner_id:
        logger.warning("skip malformed index event: %s", event)
        return

    conv = await search_svc.conv_repo.find_conversation_by_id(conversation_id, owner_id)
    if not conv:
        logger.warning("skip missing conversation. conversation_id=%s owner_id=%s", conversation_id, owner_id)
        return
    if conv.qdrant_id:
        logger.info("skip already indexed conversation. conversation_id=%s qdrant_id=%s", conversation_id, conv.qdrant_id)
        return

    cost = await search_svc.embed_conversation(conversation_id, owner_id)
    logger.info("indexed conversation. conversation_id=%s cost_usd=%s", conversation_id, cost)


async def run_worker() -> None:
    if not settings.kafka_enabled:
        logger.warning("KAFKA_ENABLED is false. conversation index worker is idle.")
        return
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for the conversation index worker.")

    mongo = AsyncIOMotorClient(settings.mongodb_url)
    qdrant = AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
    )
    consumer = AIOKafkaConsumer(
        settings.kafka_conversation_index_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_conversation_index_group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
    )

    search_svc = SearchService(
        ConversationRepository(mongo[settings.mongodb_db]),
        VectorRepository(qdrant),
        AsyncOpenAI(api_key=settings.openai_api_key),
    )

    await consumer.start()
    logger.info(
        "conversation index worker started. topic=%s group_id=%s bootstrap=%s",
        settings.kafka_conversation_index_topic,
        settings.kafka_conversation_index_group_id,
        settings.kafka_bootstrap_servers,
    )
    try:
        async for message in consumer:
            try:
                await _handle_event(message.value, search_svc)
            except Exception:
                logger.exception("conversation index event failed. offset=%s value=%s", message.offset, message.value)
            finally:
                await consumer.commit()
    finally:
        await consumer.stop()
        mongo.close()
        await qdrant.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("conversation index worker stopped.")
