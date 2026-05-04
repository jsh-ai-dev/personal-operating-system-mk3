# [API] 뉴스 스크래핑 및 기사 조회·분석 엔드포인트
# POST /news/scrape  — 날짜 지정 스크랩 (1~5면 자동 수집 + companies/tags 추출)
# GET  /news         — 날짜별 기사 목록 (면, 기업명, 태그 포함)
# GET  /news/{id}    — 기사 상세 (본문 전체)
# POST /news/{id}/analyze — AI 전체 분석 생성

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.adapter.mongodb.article_repository import ArticleRepository
from app.application.news_service import NewsService
from app.core.auth import AuthUser, get_current_user
from app.core.dependencies import get_db

router = APIRouter(prefix="/news", tags=["news"])


class ScrapeRequest(BaseModel):
    date: str  # "2026-05-04"


def _get_svc(db: AsyncIOMotorDatabase = Depends(get_db)) -> NewsService:
    return NewsService(ArticleRepository(db))


@router.post("/scrape")
async def scrape_news(
    body: ScrapeRequest,
    svc: NewsService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    articles = await svc.scrape(body.date, user.id)
    return [asdict(a) for a in articles]


@router.get("")
async def list_news(
    date: str,
    svc: NewsService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    articles = await svc.list_by_date(date, user.id)
    return [asdict(a) for a in articles]


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
    svc: NewsService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    article = await svc.analyze(id, user.id)
    if not article:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
    return asdict(article)
