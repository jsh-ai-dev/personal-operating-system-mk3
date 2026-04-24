# [Codex 스크래퍼] chatgpt.com 내부 API를 통해 Codex 할당량 정보를 읽어오는 모듈
# ChatGPT 스크래퍼와 동일한 CDP 방식으로 동작하며, chatgpt.com 세션을 공유함
# Codex는 ChatGPT 플랜에 포함되지만 사용량 한도는 별도 추적됨 —
# /backend-api/wham/usage 가 5시간/7일 창 기준 잔여 할당량을 반환함

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


def _is_chrome_running() -> bool:
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

    for _ in range(20):
        time.sleep(0.5)
        if _is_chrome_running():
            break
    else:
        return False

    deadline = time.time() + 6.0
    while time.time() < deadline:
        time.sleep(0.3)
        new_windows = _get_visible_window_handles() - windows_before
        if new_windows:
            _hide_windows(new_windows)

    return True


def _fetch_via_browser_raw(page, url: str, access_token: str | None = None) -> dict:
    # 에러 포함 원본 응답을 그대로 반환 — 디버깅용
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
                const text = await res.text();
                let body;
                try {{ body = JSON.parse(text); }} catch {{ body = text; }}
                return {{ status: res.status, ok: res.ok, body }};
            }} catch (e) {{
                return {{ status: 0, ok: false, body: e.message }};
            }}
        }}
    """)
    return result or {}


def _scrape_sync() -> dict:
    if not _is_chrome_running():
        if not _launch_chrome():
            raise RuntimeError("Chrome 실행에 실패했습니다.")

    windows_before = _get_visible_window_handles()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()

        time.sleep(0.3)
        _hide_windows(_get_visible_window_handles() - windows_before)

        try:
            page.goto('https://chatgpt.com', wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(1000)

            session_raw = _fetch_via_browser_raw(page, 'https://chatgpt.com/api/auth/session')
            session = session_raw.get('body') if session_raw.get('ok') else None
            if not session or not isinstance(session, dict) or not session.get('user'):
                return {'login_required': True}

            access_token = session.get('accessToken')

            # Codex 전용 할당량 엔드포인트 — Codex CLI가 ~60초마다 폴링하는 내부 API
            wham_raw = _fetch_via_browser_raw(page, 'https://chatgpt.com/backend-api/wham/usage', access_token)
            wham = wham_raw.get('body') if wham_raw.get('ok') else None

            # ChatGPT와 동일 구독이므로 accounts/check에서 결제일 정보 가져오기
            sub_raw = _fetch_via_browser_raw(
                page,
                'https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27',
                access_token,
            )
            sub = sub_raw.get('body') if sub_raw.get('ok') else None

            return {
                'login_required': False,
                **_parse_result(wham, sub),
            }
        finally:
            page.close()
            _hide_windows(_get_visible_window_handles() - windows_before)


def _parse_result(wham: dict | None, sub: dict | None = None) -> dict:
    result = {}

    if wham:
        rate_limit = wham.get('rate_limit') or {}
        primary = rate_limit.get('primary_window') or {}
        secondary = rate_limit.get('secondary_window') or {}

        if primary.get('used_percent') is not None:
            result['primary_usage_pct'] = int(primary['used_percent'])
        if primary.get('reset_at'):
            result['primary_reset_at'] = _unix_to_iso(primary['reset_at'])
        if secondary.get('used_percent') is not None:
            result['secondary_usage_pct'] = int(secondary['used_percent'])
        if secondary.get('reset_at'):
            result['secondary_reset_at'] = _unix_to_iso(secondary['reset_at'])
        if wham.get('plan_type'):
            result['plan_type'] = wham['plan_type']

        credits = wham.get('credits') or {}
        result['has_credits'] = credits.get('has_credits', False)
        result['credit_balance'] = credits.get('balance', '0')

    if sub:
        entitlement = sub.get('accounts', {}).get('default', {}).get('entitlement', {})
        for key in ('renews_at', 'expires_at', 'cancels_at'):
            val = entitlement.get(key)
            if val:
                result['next_billing_date'] = str(val)
                break

    return result


def _unix_to_iso(ts: int) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


async def scrape_codex() -> dict:
    return await asyncio.to_thread(_scrape_sync)
