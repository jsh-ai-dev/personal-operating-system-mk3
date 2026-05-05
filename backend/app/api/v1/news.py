# [API] 뉴스 스크래핑 및 기사 조회·분석 엔드포인트
# GET  /news/models       — 분석에 사용 가능한 OpenAI 모델 목록 (가격 포함)
# POST /news/scrape       — 날짜 지정 스크랩 (1~5면 자동 수집 + companies/tags 추출)
# GET  /news              — 날짜별 기사 목록 (면, 기업명, 태그 포함)
# GET  /news/{id}         — 기사 상세 (본문 전체)
# POST /news/{id}/analyze — AI 전체 분석 생성 (model 선택 가능)

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.adapter.mongodb.article_repository import ArticleRepository
from app.application.chat_service import OPENAI_PRICING
from app.application.news_service import DEFAULT_MODEL, NewsService
from app.core.auth import AuthUser, get_current_user
from app.core.dependencies import get_db

router = APIRouter(prefix="/news", tags=["news"])


class ScrapeRequest(BaseModel):
    date: str  # "2026-05-04"


class AnalyzeRequest(BaseModel):
    model: str = DEFAULT_MODEL


def _get_svc(db: AsyncIOMotorDatabase = Depends(get_db)) -> NewsService:
    return NewsService(ArticleRepository(db))


@router.post("/scrape")
async def scrape_news(
    body: ScrapeRequest,
    svc: NewsService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    try:
        articles = await svc.scrape(body.date, user.id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return [asdict(a) for a in articles]


@router.get("")
async def list_news(
    date: str | None = None,
    company: str | None = None,
    tag: str | None = None,
    svc: NewsService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    # company 또는 tag가 있으면 전체 기간 검색, 없으면 날짜 기준 조회
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
    """전체 기간에 걸쳐 분석된 기업명·태그 목록 반환 (필터 드롭다운용)"""
    return await svc.get_filter_options(user.id)


@router.get("/models")
async def get_news_models():
    """뉴스 분석에 사용할 수 있는 OpenAI 모델 목록과 가격 반환"""
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
    user: AuthUser = Depends(get_current_user),
):
    if body.model not in OPENAI_PRICING:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 모델: {body.model}")
    article = await svc.analyze(id, user.id, body.model)
    if not article:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
    return asdict(article)
