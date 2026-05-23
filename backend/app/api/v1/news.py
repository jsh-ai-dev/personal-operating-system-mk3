# [API] 뉴스 스크래핑 및 기사 조회/분석 엔드포인트
# GET  /news/models       - 분석에 사용 가능한 OpenAI 모델 목록
# POST /news/scrape       - 날짜 지정 스크랩 job 생성 후 Kafka 이벤트 발행
# GET  /news              - 날짜/기업/태그 기준 기사 목록
# GET  /news/{id}         - 기사 상세
# POST /news/{id}/analyze - AI 분석 Kafka 이벤트 발행

from dataclasses import asdict
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.adapter.mongodb.article_repository import ArticleRepository
from app.adapter.mongodb.news_scrape_job_repository import NewsScrapeJobRepository
from app.application.chat_service import OPENAI_PRICING
from app.application.news_events import NewsEventPublisher
from app.application.news_service import DEFAULT_MODEL, NewsService
from app.core.auth import AuthUser, get_current_user
from app.core.dependencies import get_db, get_news_event_publisher

router = APIRouter(prefix="/news", tags=["news"])
logger = logging.getLogger(__name__)


class ScrapeRequest(BaseModel):
    date: str


class AnalyzeRequest(BaseModel):
    model: str = DEFAULT_MODEL


def _get_svc(db: AsyncIOMotorDatabase = Depends(get_db)) -> NewsService:
    return NewsService(ArticleRepository(db), NewsScrapeJobRepository(db))


@router.post("/scrape")
async def scrape_news(
    body: ScrapeRequest,
    background_tasks: BackgroundTasks,
    svc: NewsService = Depends(_get_svc),
    news_publisher: NewsEventPublisher = Depends(get_news_event_publisher),
    user: AuthUser = Depends(get_current_user),
):
    try:
        job, started = await svc.start_scrape_job(body.date, user.id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    if started:
        try:
            published = await news_publisher.publish_scrape_requested(job["id"], body.date, user.id)
        except Exception as e:
            logger.warning("publish news scrape event failed for job %s: %s", job["id"], e)
            published = False
        if not published:
            background_tasks.add_task(svc.run_scrape_job, job["id"], body.date, user.id)

    articles = await svc.list_by_date(body.date, user.id)
    return {
        "articles": [asdict(a) for a in articles],
        "new_count": job.get("inserted", 0),
        "job": job,
        "started": started,
    }


@router.get("/scrape/jobs/latest")
async def get_latest_scrape_job(
    date: str | None = None,
    svc: NewsService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    job = await svc.get_latest_scrape_job(user.id, date)
    if not job:
        raise HTTPException(status_code=404, detail="Scrape job not found.")
    return job


@router.get("/scrape/jobs/{job_id}")
async def get_scrape_job(
    job_id: str,
    svc: NewsService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    job = await svc.get_scrape_job(job_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Scrape job not found.")
    return job


@router.get("/dates")
async def get_news_dates(
    svc: NewsService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return await svc.repo.find_all_dates(user.id)


@router.get("")
async def list_news(
    date: str | None = None,
    company: str | None = None,
    tag: str | None = None,
    svc: NewsService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    if company or tag:
        articles = await svc.list_by_filter(user.id, company, tag)
    elif date:
        articles = await svc.list_by_date(date, user.id)
    else:
        raise HTTPException(status_code=400, detail="date 또는 company/tag 파라미터가 필요합니다.")
    return [asdict(a) for a in articles]


@router.get("/filter-options")
async def get_filter_options(
    svc: NewsService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return await svc.get_filter_options(user.id)


@router.get("/models")
async def get_news_models():
    models = [
        {"id": model_id, "input_per_1m": p["input"], "output_per_1m": p["output"]}
        for model_id, p in OPENAI_PRICING.items()
    ]
    return sorted(models, key=lambda m: m["input_per_1m"])


@router.get("/{id}")
async def get_news(
    id: str,
    svc: NewsService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    article = await svc.get(id, user.id)
    if not article:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
    return asdict(article)


@router.post("/{id}/analyze")
async def analyze_news(
    id: str,
    body: AnalyzeRequest,
    svc: NewsService = Depends(_get_svc),
    news_publisher: NewsEventPublisher = Depends(get_news_event_publisher),
    user: AuthUser = Depends(get_current_user),
):
    if body.model not in OPENAI_PRICING:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 모델: {body.model}")

    article = await svc.get(id, user.id)
    if not article:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")

    try:
        published = await news_publisher.publish_analysis_requested(id, user.id, body.model)
    except Exception as e:
        logger.warning("publish news analysis event failed for article %s: %s", id, e)
        published = False

    if not published:
        article = await svc.analyze(id, user.id, body.model)
        if not article:
            raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")

    return asdict(article)
