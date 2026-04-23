# [스크래퍼 API] POST /api/v1/scraper/claude — Claude.ai 구독 정보를 자동으로 읽어오는 엔드포인트
# 세션 쿠키(.env의 CLAUDE_SESSION_COOKIE)를 사용해 Playwright로 페이지를 긁어옴

import traceback

from fastapi import APIRouter, HTTPException

from app.adapter.scraper.claude_scraper import scrape_claude_billing
from app.core.config import settings

router = APIRouter(prefix="/scraper", tags=["scraper"])


@router.post("/claude")
async def scrape_claude():
    if not settings.claude_session_cookie:
        raise HTTPException(
            status_code=400,
            detail="CLAUDE_SESSION_COOKIE가 설정되지 않았습니다. backend/.env 파일을 확인하세요.",
        )

    try:
        result = await scrape_claude_billing(
            cookie_name=settings.claude_cookie_name,
            cookie_value=settings.claude_session_cookie,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    return result
