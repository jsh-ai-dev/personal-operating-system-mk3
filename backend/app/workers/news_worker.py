import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from motor.motor_asyncio import AsyncIOMotorClient

from app.adapter.mongodb.article_repository import ArticleRepository
from app.adapter.mongodb.news_scrape_job_repository import NewsScrapeJobRepository
from app.application.news_events import NEWS_ANALYSIS_REQUESTED_EVENT_TYPE, NEWS_SCRAPE_REQUESTED_EVENT_TYPE
from app.application.news_service import DEFAULT_MODEL, NewsService
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logging.getLogger("aiokafka").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def _handle_scrape_event(event: dict, news_svc: NewsService) -> None:
    job_id = event.get("job_id")
    date = event.get("date")
    owner_id = event.get("owner_id")

    if not job_id or not date or not owner_id:
        logger.warning("skip malformed news scrape event: %s", event)
        return

    job = await news_svc.get_scrape_job(job_id, owner_id)
    if not job:
        logger.warning("skip missing news scrape job. job_id=%s owner_id=%s", job_id, owner_id)
        return
    if job.get("status") not in {"queued", "running"}:
        logger.info("skip finished news scrape job. job_id=%s status=%s", job_id, job.get("status"))
        return

    await news_svc.run_scrape_job(job_id, date, owner_id)
    logger.info("completed news scrape job. job_id=%s date=%s", job_id, date)


async def _handle_analysis_event(event: dict, news_svc: NewsService) -> None:
    article_id = event.get("article_id")
    owner_id = event.get("owner_id")
    model = event.get("model") or DEFAULT_MODEL

    if not article_id or not owner_id:
        logger.warning("skip malformed news analysis event: %s", event)
        return

    article = await news_svc.analyze(article_id, owner_id, model)
    if not article:
        logger.warning("skip missing news article. article_id=%s owner_id=%s", article_id, owner_id)
        return

    cost = article.analysis.analysis_cost_usd if article.analysis else 0.0
    logger.info("analyzed news article. article_id=%s model=%s cost_usd=%s", article_id, model, cost)


async def _handle_event(event: dict, news_svc: NewsService) -> None:
    event_type = event.get("event_type")
    if event_type == NEWS_SCRAPE_REQUESTED_EVENT_TYPE:
        await _handle_scrape_event(event, news_svc)
        return
    if event_type == NEWS_ANALYSIS_REQUESTED_EVENT_TYPE:
        await _handle_analysis_event(event, news_svc)
        return
    logger.warning("skip unsupported news event type: %s", event_type)


async def run_worker() -> None:
    if not settings.kafka_enabled:
        logger.warning("KAFKA_ENABLED is false. news worker is idle.")
        return

    mongo = AsyncIOMotorClient(settings.mongodb_url)
    consumer = AIOKafkaConsumer(
        settings.kafka_news_scrape_topic,
        settings.kafka_news_analysis_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_news_group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
    )
    news_svc = NewsService(ArticleRepository(mongo[settings.mongodb_db]), NewsScrapeJobRepository(mongo[settings.mongodb_db]))

    await consumer.start()
    logger.info(
        "news worker started. scrape_topic=%s analysis_topic=%s group_id=%s bootstrap=%s",
        settings.kafka_news_scrape_topic,
        settings.kafka_news_analysis_topic,
        settings.kafka_news_group_id,
        settings.kafka_bootstrap_servers,
    )
    try:
        async for message in consumer:
            try:
                await _handle_event(message.value, news_svc)
            except Exception:
                logger.exception("news event failed. offset=%s value=%s", message.offset, message.value)
            finally:
                await consumer.commit()
    finally:
        await consumer.stop()
        mongo.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("news worker stopped.")
