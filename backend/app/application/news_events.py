import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

NEWS_SCRAPE_REQUESTED_EVENT_TYPE = "news.scrape_requested.v1"
NEWS_ANALYSIS_REQUESTED_EVENT_TYPE = "news.analysis_requested.v1"


class NewsEventPublisher:
    async def publish_scrape_requested(self, job_id: str, date: str, owner_id: str) -> bool:
        raise NotImplementedError

    async def publish_analysis_requested(self, article_id: str, owner_id: str, model: str) -> bool:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


class NoopNewsEventPublisher(NewsEventPublisher):
    async def publish_scrape_requested(self, job_id: str, date: str, owner_id: str) -> bool:
        return False

    async def publish_analysis_requested(self, article_id: str, owner_id: str, model: str) -> bool:
        return False


class KafkaNewsEventPublisher(NewsEventPublisher):
    def __init__(self, bootstrap_servers: str, scrape_topic: str, analysis_topic: str):
        self.bootstrap_servers = bootstrap_servers
        self.scrape_topic = scrape_topic
        self.analysis_topic = analysis_topic
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

    async def publish_scrape_requested(self, job_id: str, date: str, owner_id: str) -> bool:
        event = {
            "event_id": str(uuid4()),
            "event_type": NEWS_SCRAPE_REQUESTED_EVENT_TYPE,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "owner_id": owner_id,
            "job_id": job_id,
            "date": date,
        }
        producer = await self._get_producer()
        await producer.send_and_wait(self.scrape_topic, event, key=job_id)
        logger.info("published news scrape event. job_id=%s date=%s", job_id, date)
        return True

    async def publish_analysis_requested(self, article_id: str, owner_id: str, model: str) -> bool:
        event = {
            "event_id": str(uuid4()),
            "event_type": NEWS_ANALYSIS_REQUESTED_EVENT_TYPE,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "owner_id": owner_id,
            "article_id": article_id,
            "model": model,
        }
        producer = await self._get_producer()
        await producer.send_and_wait(self.analysis_topic, event, key=article_id)
        logger.info("published news analysis event. article_id=%s model=%s", article_id, model)
        return True

    async def aclose(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
