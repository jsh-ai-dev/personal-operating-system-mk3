# [Claude 스크래퍼] claude.ai 설정 페이지에서 구독 정보를 자동으로 읽어오는 모듈
# CDP(Chrome DevTools Protocol)로 크롬에 연결해 페이지를 읽음
# Windows API(ctypes)로 크롬 창을 완전히 숨겨 작업표시줄에서도 보이지 않게 함

import asyncio
import ctypes
import ctypes.wintypes
import re
import socket
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CDP_PORT = 9222
CHROME_USER_DATA_DIR = r"C:\temp\chrome-debug"
_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


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
    # SW_HIDE 대신 화면 밖으로 이동 — SW_HIDE는 Chrome 렌더러를 절전시켜 screenshot이 타임아웃남
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW = 0x00040000
    SWP_NOACTIVATE = 0x0010
    for hwnd in handles:
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new_style = (ex_style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        SWP_NOSIZE = 0x0001
        ctypes.windll.user32.SetWindowPos(hwnd, 0, -32000, -32000, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE)


def _launch_chrome() -> bool:
    chrome = _find_chrome_path()
    if not chrome:
        raise RuntimeError("Chrome을 찾을 수 없습니다. Chrome이 설치됐는지 확인하세요.")

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
        windows_after = _get_visible_window_handles()
        new_windows = windows_after - windows_before
        if new_windows:
            _hide_windows(new_windows)

    return True


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
            page.goto('https://claude.ai/settings/billing', wait_until='load', timeout=30000)
            page.wait_for_timeout(500)
            billing_text = page.inner_text('body')

            if _is_login_required(billing_text):
                return {'login_required': True}

            page.goto('https://claude.ai/settings/usage', wait_until='networkidle', timeout=30000)
            usage_text = page.inner_text('body')

            return {
                'login_required': False,
                'plan_name': _extract_plan(billing_text),
                'next_billing_date': _extract_billing_date(billing_text),
                **_extract_usage(usage_text),
            }
        finally:
            page.close()
            # 스크래핑 완료 후 남은 새 창 정리 / 크롬은 닫지 않음 — 백그라운드에서 계속 유지
            _hide_windows(_get_visible_window_handles() - windows_before)


async def scrape_claude() -> dict:
    # asyncio.to_thread: 동기 함수를 별도 스레드에서 실행해 FastAPI 이벤트 루프를 블로킹하지 않음
    return await asyncio.to_thread(_scrape_sync)


def _is_login_required(text: str) -> bool:
    has_plan = any(p in text for p in ['Pro 요금제', 'Max 요금제', 'Claude Pro', 'Claude Max'])
    return not has_plan


def _extract_plan(text: str) -> str | None:
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

    session_pct = re.search(r'현재 세션.{0,50}?(\d+)% 사용됨', text, re.DOTALL)
    if session_pct:
        result['session_usage_pct'] = int(session_pct.group(1))

    reset_in = re.search(r'(\d+시간 \d+분|\d+시간|\d+분) 후 재설정', text)
    if reset_in:
        result['session_reset_in'] = reset_in.group(1)

    weekly_pct = re.search(r'모든 모델.{0,80}?(\d+)% 사용됨', text, re.DOTALL)
    if weekly_pct:
        result['weekly_usage_pct'] = int(weekly_pct.group(1))

    weekly_reset = re.search(r'(\([가-힣]+\) [^\n]+에 재설정)', text)
    if weekly_reset:
        result['weekly_reset_at'] = weekly_reset.group(1)

    return result


def _extract_billing_date(text: str) -> str | None:
    patterns = [
        r'(\d{4}년 \d{1,2}월 \d{1,2}일)',
        r'(?:renews?|next billing|billed)[^\n]{0,30}?([A-Z][a-z]+ \d{1,2},? \d{4})',
        r'(\d{4}-\d{2}-\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None
