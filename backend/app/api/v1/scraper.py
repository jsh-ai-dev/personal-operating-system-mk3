# [스크래퍼 API] POST /api/v1/scraper/{claude,chatgpt} — AI 서비스 구독/사용량 정보를 읽어오는 엔드포인트
# CDP로 연결된 크롬을 통해 스크래핑하고, 결과를 DB의 AI 서비스 레코드에 자동 반영함

import re
import traceback
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.adapter.mongodb.ai_service_repository import AIServiceRepository
from app.adapter.scraper.claude_scraper import scrape_claude
from app.adapter.scraper.chatgpt_scraper import scrape_chatgpt
from app.adapter.scraper.codex_scraper import scrape_codex
from app.adapter.scraper.gemini_scraper import scrape_gemini
from app.adapter.scraper.cursor_scraper import scrape_cursor
from app.core.auth import AuthUser, get_current_user
from app.core.dependencies import get_db

router = APIRouter(prefix="/scraper", tags=["scraper"])


@router.post("/claude")
async def trigger_claude_scrape(
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    try:
        result = await scrape_claude()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    # 로그인이 필요한 상태면 프론트엔드에 알림
    if result.get('login_required'):
        return {'login_required': True, 'message': '크롬에서 claude.ai 로그인이 필요합니다.'}

    # DB에서 Claude 서비스 레코드를 찾아 스크래핑 결과로 업데이트
    repo = AIServiceRepository(db)
    service = await repo.find_by_name('Claude', user.id)
    if service:
        update_data = {}

        if result.get('plan_name'):
            update_data['plan_name'] = result['plan_name']

        # "2026년 5월 22일" → billing_day: 22
        billing_day = _parse_billing_day(result.get('next_billing_date'))
        if billing_day:
            update_data['billing_day'] = billing_day

        # 현재 세션 사용량을 usage_current/limit에 반영
        if result.get('session_usage_pct') is not None:
            update_data['usage_current'] = result['session_usage_pct']
            update_data['usage_limit'] = 100
            reset_info = result.get('session_reset_in', '')
            update_data['usage_unit'] = f"% (세션, {reset_info} 후 리셋)" if reset_info else "% (현재 세션)"

        if update_data:
            await repo.update(service.id, update_data, user.id)

    return result


@router.post("/chatgpt")
async def trigger_chatgpt_scrape(
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    try:
        result = await scrape_chatgpt()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    if result.get('login_required'):
        return {'login_required': True, 'message': '크롬에서 chatgpt.com 로그인이 필요합니다.'}

    repo = AIServiceRepository(db)
    service = await repo.find_by_name('ChatGPT', user.id)
    if service:
        update_data = {}

        if result.get('plan_name'):
            update_data['plan_name'] = result['plan_name']

        billing_day = _parse_billing_day(result.get('next_billing_date'))
        if billing_day:
            update_data['billing_day'] = billing_day

        if result.get('next_billing_date'):
            update_data['next_billing_date'] = result['next_billing_date']

        if update_data:
            await repo.update(service.id, update_data, user.id)

    return {k: v for k, v in result.items() if k != '_raw'}


@router.post("/codex")
async def trigger_codex_scrape(
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    try:
        result = await scrape_codex()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    if result.get('login_required'):
        return {'login_required': True, 'message': '크롬에서 chatgpt.com 로그인이 필요합니다.'}

    repo = AIServiceRepository(db)
    service = await repo.find_by_name('Codex', user.id)
    if service:
        update_data = {}

        _PLAN_MAP = {'plus': 'ChatGPT Plus', 'pro': 'ChatGPT Pro', 'team': 'ChatGPT Team'}
        if result.get('plan_type'):
            update_data['plan_name'] = _PLAN_MAP.get(result['plan_type'], result['plan_type'].capitalize())

        billing_day = _parse_billing_day(result.get('next_billing_date'))
        if billing_day:
            update_data['billing_day'] = billing_day

        if result.get('next_billing_date'):
            update_data['next_billing_date'] = result['next_billing_date']

        # 5시간 창 사용률을 usage_current/limit에 반영
        if result.get('primary_usage_pct') is not None:
            update_data['usage_current'] = result['primary_usage_pct']
            update_data['usage_limit'] = 100
            reset_iso = result.get('primary_reset_at', '')
            reset_label = _format_reset_label(reset_iso)
            update_data['usage_unit'] = f"% (5h 창{reset_label})"

        if update_data:
            await repo.update(service.id, update_data, user.id)

    return result


@router.post("/gemini")
async def trigger_gemini_scrape(
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    try:
        result = await scrape_gemini()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    if result.get('login_required'):
        return {'login_required': True, 'message': '크롬에서 gemini.google.com 로그인이 필요합니다.'}

    repo = AIServiceRepository(db)
    service = await repo.find_by_name('Gemini', user.id)
    if service:
        update_data = {}

        if result.get('plan_name'):
            update_data['plan_name'] = result['plan_name']

        billing_day = _parse_billing_day(result.get('next_billing_date'))
        if billing_day:
            update_data['billing_day'] = billing_day

        if result.get('next_billing_date'):
            update_data['next_billing_date'] = result['next_billing_date']

        if update_data:
            await repo.update(service.id, update_data, user.id)

    return result


@router.post("/cursor")
async def trigger_cursor_scrape(
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    try:
        result = await scrape_cursor()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    if result.get('login_required'):
        return {'login_required': True, 'message': '크롬에서 cursor.com 로그인이 필요합니다.'}

    repo = AIServiceRepository(db)
    service = await repo.find_by_name('Cursor', user.id)
    if service:
        update_data = {}

        if result.get('plan_name'):
            update_data['plan_name'] = result['plan_name']

        billing_day = _parse_billing_day(result.get('next_billing_date'))
        if billing_day:
            update_data['billing_day'] = billing_day

        if result.get('next_billing_date'):
            update_data['next_billing_date'] = result['next_billing_date']

        if result.get('monthly_cost') is not None:
            update_data['monthly_cost'] = result['monthly_cost']

        if result.get('usage_current') is not None:
            update_data['usage_current'] = result['usage_current']
            update_data['usage_limit'] = result['usage_limit']
            update_data['usage_unit'] = result.get('usage_unit', '%')

        if update_data:
            await repo.update(service.id, update_data, user.id)

    return result


def _format_reset_label(iso: str) -> str:
    if not iso:
        return ''
    try:
        dt = datetime.fromisoformat(iso).astimezone(timezone(timedelta(hours=9)))
        return f", {dt.strftime('%m/%d %H:%M')} 리셋"
    except ValueError:
        return ''


def _parse_billing_day(date_str: str | None) -> int | None:
    if not date_str:
        return None
    # "2026년 5월 22일" → 22
    m = re.search(r'(\d{1,2})일', date_str)
    if m:
        return int(m.group(1))
    # "2026-05-14T21:29:22+00:00" → UTC를 KST(+9)로 변환 후 일 추출
    try:
        dt = datetime.fromisoformat(date_str)
        kst = dt.astimezone(timezone(timedelta(hours=9)))
        return kst.day
    except ValueError:
        pass
    return None
