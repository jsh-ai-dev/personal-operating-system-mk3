# [Claude 스크래퍼] claude.ai 설정 페이지에서 구독 정보를 자동으로 읽어오는 모듈
# Playwright로 브라우저를 headless(창 없이) 실행해 로그인된 페이지에 접근함
# 쿠키를 직접 주입하므로 아이디/비밀번호 없이 기존 세션을 재사용함

import asyncio
import re
from pathlib import Path

from playwright.sync_api import sync_playwright


def _scrape_sync(cookie_name: str, cookie_value: str) -> dict:
    # 동기(sync) Playwright API 사용
    # Windows의 asyncio SelectorEventLoop은 서브프로세스 생성을 지원하지 않아
    # async_playwright가 브라우저를 실행하지 못함 → 동기 방식으로 우회
    with sync_playwright() as p:
        # connect_over_cdp: 새 브라우저를 실행하는 대신 사용자가 이미 열어놓은 크롬에 연결
        # 진짜 크롬이므로 Cloudflare 봇 탐지를 우회할 수 있음
        # 사전 조건: 크롬을 --remote-debugging-port=9222 옵션으로 실행해야 함
        browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        context = browser.contexts[0] if browser.contexts else browser.new_context()

        page = context.new_page()

        try:
            debug_dir = Path('debug')
            debug_dir.mkdir(exist_ok=True)

            # 결제 페이지 직접 접근
            page.goto('https://claude.ai/settings/billing', wait_until='load', timeout=30000)
            page.wait_for_timeout(2000)
            page.screenshot(path='debug/claude_billing.png', full_page=True)
            billing_text = page.inner_text('body')

            # 사용량 페이지 직접 접근
            page.goto('https://claude.ai/settings/usage', wait_until='load', timeout=30000)
            page.wait_for_timeout(2000)
            page.screenshot(path='debug/claude_usage.png', full_page=True)
            usage_text = page.inner_text('body')

            return {
                'plan_name': _extract_plan(billing_text),
                'next_billing_date': _extract_billing_date(billing_text),
                **_extract_usage(usage_text),
            }
        finally:
            page.close()


async def scrape_claude_billing(cookie_name: str, cookie_value: str) -> dict:
    # asyncio.to_thread: 동기 함수를 별도 스레드에서 실행해 FastAPI 이벤트 루프를 블로킹하지 않음
    return await asyncio.to_thread(_scrape_sync, cookie_name, cookie_value)


def _extract_plan(text: str) -> str | None:
    # 한국어/영어 플랜명 모두 처리
    plan_patterns = [
        (r'Claude\s*Max', 'Claude Max'),
        (r'Claude\s*Pro', 'Claude Pro'),
        (r'Max\s*요금제', 'Claude Max'),
        (r'Pro\s*요금제', 'Claude Pro'),
        (r'Free\s*요금제|무료\s*요금제', 'Free'),
    ]
    for pattern, plan_name in plan_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return plan_name
    return None


def _extract_usage(text: str) -> dict:
    result = {}

    # 현재 세션 사용량 (%) — "현재 세션 ... 79% 사용됨"
    session_pct = re.search(r'현재 세션.{0,50}?(\d+)% 사용됨', text, re.DOTALL)
    if session_pct:
        result['session_usage_pct'] = int(session_pct.group(1))

    # 세션 리셋까지 남은 시간 — "2시간 47분 후 재설정" 또는 "30분 후 재설정"
    reset_in = re.search(r'(\d+시간 \d+분|\d+시간|\d+분) 후 재설정', text)
    if reset_in:
        result['session_reset_in'] = reset_in.group(1)

    # 주간 전체 사용량 (%) — "모든 모델 ... 14% 사용됨"
    weekly_pct = re.search(r'모든 모델.{0,80}?(\d+)% 사용됨', text, re.DOTALL)
    if weekly_pct:
        result['weekly_usage_pct'] = int(weekly_pct.group(1))

    # 주간 리셋 시점 — "(목) 오전 12:00에 재설정"
    weekly_reset = re.search(r'(\([가-힣]+\) [^\n]+에 재설정)', text)
    if weekly_reset:
        result['weekly_reset_at'] = weekly_reset.group(1)

    return result


def _extract_billing_date(text: str) -> str | None:
    # 한국어/영어 날짜 표현 모두 처리
    patterns = [
        # 한국어: "구독이 2026년 5월 22일에 자동으로 갱신됩니다"
        r'(\d{4}년 \d{1,2}월 \d{1,2}일)',
        # 영어: "Renews May 15, 2026" / "Next billing June 1, 2026"
        r'(?:renews?|next billing|billed)[^\n]{0,30}?([A-Z][a-z]+ \d{1,2},? \d{4})',
        # ISO 형식: "2026-05-22"
        r'(\d{4}-\d{2}-\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None
