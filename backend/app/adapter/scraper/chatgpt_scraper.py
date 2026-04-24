# [ChatGPT 스크래퍼] chatgpt.com 내부 API를 통해 구독/결제 정보를 읽어오는 모듈
# Claude 스크래퍼와 동일하게 CDP(Chrome DevTools Protocol)로 실제 Chrome 세션에 붙어 동작함
# chatgpt.com은 Cloudflare를 사용하나 Claude.ai보다 탐지 수준이 낮음 —
# 그럼에도 headless 방식은 403을 반환하므로 CDP로 실제 Chrome을 재사용함
#
# 인증 흐름:
#   1. /api/auth/session → 로그인 여부 확인 + accessToken 획득
#   2. accessToken을 Bearer 토큰으로 /backend-api/accounts/check 호출
#      (토큰 없이 호출하면 guest 뷰를 반환해 구독 정보가 비어 있음)

import asyncio
import socket
import subprocess
import time
import ctypes
import ctypes.wintypes
from pathlib import Path

from playwright.sync_api import sync_playwright

CDP_PORT = 9222
CHROME_USER_DATA_DIR = r"C:\temp\chrome-debug"
_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

_PLAN_MAP = {
    'plus': 'ChatGPT Plus',
    'pro': 'ChatGPT Pro',
    'team': 'ChatGPT Team',
    'enterprise': 'ChatGPT Enterprise',
    'free': 'Free',
}


def _is_chrome_running() -> bool:
    # CDP 포트에 연결 가능한지 확인해 크롬 실행 여부 판단
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect(('127.0.0.1', CDP_PORT))
            return True
        except (ConnectionRefusedError, OSError):
            return False


def _find_chrome_path() -> str | None:
    for path in _CHROME_PATHS:
        if Path(path).exists():
            return path
    return None


def _get_visible_window_handles() -> set:
    # 현재 화면에 표시 중인 창 핸들을 모두 수집
    handles = set()

    def callback(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            handles.add(hwnd)
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    ctypes.windll.user32.EnumWindows(EnumWindowsProc(callback), 0)
    return handles


def _hide_windows(handles: set):
    # SW_HIDE 대신 화면 밖으로 이동 — SW_HIDE는 Chrome 렌더러를 절전시켜 page 작업이 타임아웃남
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW = 0x00040000
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
    for hwnd in handles:
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new_style = (ex_style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, -32000, -32000, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE)


def _launch_chrome() -> bool:
    chrome = _find_chrome_path()
    if not chrome:
        raise RuntimeError("Chrome을 찾을 수 없습니다.")

    # 실행 전 창 목록 기록 — 나중에 새로 생긴 창만 골라 숨기기 위함
    windows_before = _get_visible_window_handles()

    subprocess.Popen([
        chrome,
        f'--remote-debugging-port={CDP_PORT}',
        f'--user-data-dir={CHROME_USER_DATA_DIR}',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-background-timer-throttling',
        '--disable-renderer-backgrounding',
        '--disable-backgrounding-occluded-windows',
        '--window-position=-32000,-32000',
    ])

    # CDP 포트가 열릴 때까지 최대 10초 대기
    for _ in range(20):
        time.sleep(0.5)
        if _is_chrome_running():
            break
    else:
        return False

    # 새 창이 나타나는 즉시 숨기기 — Chrome은 CDP 포트 오픈 후 창이 늦게 뜰 수 있어 폴링으로 감지
    deadline = time.time() + 6.0
    while time.time() < deadline:
        time.sleep(0.3)
        new_windows = _get_visible_window_handles() - windows_before
        if new_windows:
            _hide_windows(new_windows)

    return True


def _fetch_via_browser(page, url: str, access_token: str | None = None) -> dict | None:
    # 이미 로그인된 브라우저 컨텍스트에서 fetch — 쿠키/인증이 자동으로 포함됨
    auth_header = f'"Authorization": "Bearer {access_token}",' if access_token else ''
    result = page.evaluate(f"""
        async () => {{
            try {{
                const res = await fetch('{url}', {{
                    credentials: 'include',
                    headers: {{
                        'Content-Type': 'application/json',
                        {auth_header}
                    }}
                }});
                if (!res.ok) return {{ error: res.status }};
                return await res.json();
            }} catch (e) {{
                return {{ error: e.message }};
            }}
        }}
    """)
    if result and 'error' not in result:
        return result
    return None


def _scrape_sync() -> dict:
    # 크롬이 실행 중이 아니면 자동으로 실행하고 창 숨기기
    if not _is_chrome_running():
        if not _launch_chrome():
            raise RuntimeError("Chrome 실행에 실패했습니다.")

    windows_before = _get_visible_window_handles()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()

        # new_page() 호출 시 Chrome이 창을 다시 표시할 수 있으므로 즉시 숨기기
        time.sleep(0.3)
        _hide_windows(_get_visible_window_handles() - windows_before)

        try:
            # chatgpt.com에 먼저 이동해야 same-origin fetch가 작동함
            page.goto('https://chatgpt.com', wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(1000)

            # 로그인 여부 확인
            session = _fetch_via_browser(page, 'https://chatgpt.com/api/auth/session')
            if not session or not session.get('user'):
                return {'login_required': True}

            access_token = session.get('accessToken')

            # 사용자 정보 및 구독 플랜 조회
            me = _fetch_via_browser(page, 'https://chatgpt.com/backend-api/me', access_token)

            # 구독 상세 정보 조회 — Bearer 토큰 없이 호출 시 guest 뷰를 반환하므로 토큰 필수
            subscription = _fetch_via_browser(
                page,
                'https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27',
                access_token,
            )

            return {
                'login_required': False,
                **_parse_result(session, me, subscription),
            }
        finally:
            page.close()
            # 스크래핑 완료 후 남은 새 창 정리 / 크롬은 닫지 않음 — 백그라운드에서 계속 유지
            _hide_windows(_get_visible_window_handles() - windows_before)


def _parse_result(session: dict | None, me: dict | None, subscription: dict | None) -> dict:
    result = {}

    # 이메일/이름 — session.user가 가장 신뢰할 수 있는 소스
    user = (session or {}).get('user', {})
    if user.get('email'):
        result['email'] = user['email']
    if user.get('name'):
        result['user_name'] = user['name']

    # 플랜명
    plan_raw = _extract_plan_raw(session, subscription)
    if plan_raw:
        result['plan_name'] = _PLAN_MAP.get(plan_raw.lower(), plan_raw)

    # 결제일 — subscription entitlement에서 탐색
    billing_date = _extract_billing_date(subscription)
    if billing_date:
        result['next_billing_date'] = billing_date

    return result


def _extract_plan_raw(session: dict | None, subscription: dict | None) -> str | None:
    # session.account.planType이 가장 신뢰할 수 있음
    # (accounts/check 엔드포인트는 guest를 반환하는 경우가 있어 신뢰 불가)
    if session:
        plan_type = session.get('account', {}).get('planType')
        if plan_type:
            return plan_type

    # fallback: subscription entitlement (guest/chatgptguestplan은 무시)
    if subscription:
        entitlement = subscription.get('accounts', {}).get('default', {}).get('entitlement', {})
        sub_plan = entitlement.get('subscription_plan', '')
        if sub_plan and 'guest' not in sub_plan.lower():
            return sub_plan

    return None


def _extract_billing_date(subscription: dict | None) -> str | None:
    if not subscription:
        return None
    entitlement = subscription.get('accounts', {}).get('default', {}).get('entitlement', {})
    for key in ('renews_at', 'expires_at', 'cancels_at'):
        val = entitlement.get(key)
        if val:
            return str(val)
    return None


async def scrape_chatgpt() -> dict:
    # asyncio.to_thread: 동기 함수를 별도 스레드에서 실행해 FastAPI 이벤트 루프를 블로킹하지 않음
    return await asyncio.to_thread(_scrape_sync)
