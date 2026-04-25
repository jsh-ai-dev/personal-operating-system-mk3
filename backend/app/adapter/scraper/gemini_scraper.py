# [Gemini 스크래퍼] gemini.google.com 로그인 확인 후 one.google.com에서 구독/결제 정보를 읽어오는 모듈
# ChatGPT 스크래퍼와 동일한 CDP 방식으로 동작하며, Chrome 세션을 공유함
#
# 플랜명: one.google.com 본문 텍스트에서 "AI Ultra" / "AI Pro" / "AI Plus" 키워드로 탐지
# 결제일: one.google.com의 "회원 가입일"을 기준으로 이번 달(또는 다음 달) 같은 날로 계산
#         — Google One은 가입일과 동일한 날짜에 매월 청구됨

import asyncio
import re
import socket
import subprocess
import time
import ctypes
import ctypes.wintypes
from datetime import date
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


def _extract_plan(text: str) -> str | None:
    lower = text.lower()
    if 'ai ultra' in lower:
        return 'Google AI Ultra'
    if 'ai pro' in lower:
        return 'Google AI Pro'
    if 'ai plus' in lower:
        return 'Google AI Plus'
    if 'google one' in lower:
        return 'Google One'
    return None


def _calc_next_billing_date(text: str) -> str | None:
    # "회원 가입일: 2026년 4월 1일" → 가입일과 같은 날 매월 청구
    m = re.search(r'회원\s*가입일[^\d]{0,5}\d{4}년\s*\d{1,2}월\s*(\d{1,2})일', text)
    if not m:
        return None
    day = int(m.group(1))
    today = date.today()
    try:
        billing = date(today.year, today.month, day)
    except ValueError:
        return None
    if billing <= today:
        if today.month == 12:
            billing = date(today.year + 1, 1, day)
        else:
            billing = date(today.year, today.month + 1, day)
    return billing.strftime('%Y년 %m월 %d일')


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
            # --- 1단계: Gemini 로그인 확인 ---
            page.goto('https://gemini.google.com', wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(2000)

            if 'accounts.google.com' in page.url or 'signin' in page.url.lower():
                return {'login_required': True}

            # --- 2단계: one.google.com 에서 플랜명 + 결제일 추출 ---
            page.goto('https://one.google.com', wait_until='networkidle', timeout=60000)
            page.wait_for_timeout(3000)

            body_text = page.inner_text('body')

            return {
                'login_required': False,
                'plan_name': _extract_plan(body_text),
                'next_billing_date': _calc_next_billing_date(body_text),
            }

        finally:
            page.close()
            _hide_windows(_get_visible_window_handles() - windows_before)


async def scrape_gemini() -> dict:
    return await asyncio.to_thread(_scrape_sync)
