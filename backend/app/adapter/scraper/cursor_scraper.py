# [Cursor 스크래퍼] cursor.com/settings 로드 시 발생하는 API 응답을 인터셉트해서 구독/결제 정보를 읽어오는 모듈
# ChatGPT 스크래퍼와 동일한 CDP 방식으로 동작하며, Chrome 세션을 공유함
#
# 인터셉트 대상:
#   - cursor.com/api/usage-summary       → membershipType(플랜), billingCycleEnd(결제일 ISO)
#   - cursor.com/api/dashboard/get-plan-info → planInfo.billingCycleEnd(결제일 ms 타임스탬프)

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


def _parse_result(profile: dict, billing_responses: list) -> dict:
    result = {}

    # 플랜명: membershipType 우선
    membership = profile.get('membershipType') or profile.get('planName') or profile.get('plan')
    if membership:
        result['plan_name'] = _normalize_plan(str(membership))

    # 결제일 + 사용량: billing_responses 에서 추출
    # /api/usage-summary → billingCycleEnd(결제일), individualUsage.plan.autoPercentUsed(사용률)
    # /api/dashboard/get-plan-info → planInfo.billingCycleEnd(ms 타임스탬프, fallback)
    for resp in billing_responses:
        body = resp.get('body', {})

        # /api/usage-summary
        cycle_end = body.get('billingCycleEnd')
        if cycle_end and not result.get('next_billing_date'):
            result['next_billing_date'] = str(cycle_end)

        usage_pct = (body.get('individualUsage') or {}).get('plan', {}).get('autoPercentUsed')
        if usage_pct is not None and result.get('usage_current') is None:
            result['usage_current'] = round(usage_pct, 1)
            result['usage_limit'] = 100
            result['usage_unit'] = f"% (이번 달, {_format_cycle_end(str(cycle_end))} 리셋)" if cycle_end else "% (이번 달)"

        # /api/dashboard/get-plan-info
        plan_info = body.get('planInfo', {})
        cycle_end_ms = plan_info.get('billingCycleEnd')
        if cycle_end_ms and not result.get('next_billing_date'):
            result['next_billing_date'] = _unix_to_iso(int(cycle_end_ms) // 1000)

        price_str = plan_info.get('price', '')
        if price_str and result.get('monthly_cost') is None:
            import re as _re
            m = _re.search(r'\$?([\d.]+)', price_str)
            if m:
                result['monthly_cost'] = float(m.group(1))

    return result


def _format_cycle_end(iso: str) -> str:
    from datetime import datetime, timezone, timedelta
    try:
        dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        kst = dt.astimezone(timezone(timedelta(hours=9)))
        return kst.strftime('%m/%d')
    except Exception:
        return ''


def _normalize_plan(raw: str) -> str:
    lower = raw.lower()
    if 'business' in lower:
        return 'Cursor Business'
    if 'pro+' in lower or 'pro plus' in lower or 'ultra' in lower:
        return 'Cursor Pro+'
    if 'pro' in lower:
        return 'Cursor Pro'
    if 'hobby' in lower or 'free' in lower:
        return 'Cursor Hobby'
    return raw


def _unix_to_iso(ts: int) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


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
            # 설정 페이지 이동 시 cursor.com이 호출하는 API 요청 인터셉트
            intercepted = {}

            def handle_response(response):
                url = response.url
                if ('cursor.com' in url or 'cursor.sh' in url) and response.status == 200:
                    try:
                        body = response.json()
                        # 구독 정보 응답 탐색
                        if any(k in body for k in ('membershipType', 'plan', 'subscription', 'planName', 'stripeProfile')):
                            intercepted['profile_url'] = url
                            intercepted['profile'] = body
                        # 결제일이 포함된 응답 별도 수집
                        body_str = str(body)
                        if any(k in body_str for k in ('period_end', 'billing', 'invoice', 'renewal', 'next_payment', 'current_period')):
                            intercepted.setdefault('billing_responses', []).append({'url': url, 'body': body})
                    except Exception:
                        pass

            page.on('response', handle_response)

            page.goto('https://cursor.com/settings', wait_until='networkidle', timeout=60000)
            page.wait_for_timeout(3000)

            # 로그인 여부 확인
            if 'login' in page.url.lower() or 'auth' in page.url.lower() or 'sign' in page.url.lower():
                return {'login_required': True}

            return {
                'login_required': False,
                **_parse_result(intercepted.get('profile', {}), intercepted.get('billing_responses', [])),
            }

        finally:
            page.close()
            _hide_windows(_get_visible_window_handles() - windows_before)


async def scrape_cursor() -> dict:
    return await asyncio.to_thread(_scrape_sync)
