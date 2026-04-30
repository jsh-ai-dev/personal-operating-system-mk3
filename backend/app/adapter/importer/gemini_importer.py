# [임포터] Google Takeout '내활동.json'을 파싱해 날짜별 대화 데이터 추출
# Takeout은 대화 스레드 정보 없이 Q&A 쌍을 시간순으로 나열 → 날짜별로 묶어 1개 대화로 구성

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))  # 날짜 그룹핑 기준 타임존 — Gemini Takeout은 UTC 저장이지만 제목/그룹은 사용자 로컬(KST) 기준이 자연스러움


@dataclass
class ParsedConversation:
    session_id: str  # "gemini_takeout_YYYY-MM-DD" — 중복 임포트 방지용 고유 키
    title: str       # "YYYY-MM-DD"
    messages: list[dict] = field(default_factory=list)  # [{"role", "content", "created_at"}]


def _strip_html(html: str) -> str:
    # 블록 태그를 줄바꿈으로 변환 후 나머지 태그 제거
    html = re.sub(r'</?(p|h[1-6]|li|tr|br)\b[^>]*>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<[^>]+>', '', html)
    html = re.sub(r'\n{3,}', '\n\n', html)
    return html.strip()


def _clean_title(raw: str) -> str:
    # Takeout이 모든 항목 제목 끝에 " 항목을 검색함"을 붙임 → 제거해서 실제 질문만 추출
    return re.sub(r'\s*항목을 검색함\s*$', '', raw).strip()


def parse_takeout(path: Path) -> list[ParsedConversation]:
    with open(path, encoding="utf-8") as f:
        items = json.load(f)

    # 날짜(YYYY-MM-DD) → [(datetime, item), ...] 그룹핑
    groups: dict[str, list[tuple[datetime, dict]]] = {}
    for item in items:
        time_str = item.get("time", "")
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        date_key = dt.astimezone(KST).strftime("%Y-%m-%d")  # KST 기준 날짜로 그룹핑
        groups.setdefault(date_key, []).append((dt, item))

    result = []
    for date_key, entries in sorted(groups.items()):
        entries.sort(key=lambda x: x[0])  # 시간 오름차순 정렬

        messages = []
        for dt, item in entries:
            user_text = _clean_title(item.get("title", ""))
            if not user_text:
                continue

            html_items = item.get("safeHtmlItem", [])
            assistant_text = _strip_html(html_items[0].get("html", "")) if html_items else ""

            messages.append({"role": "user", "content": user_text, "created_at": dt})
            if assistant_text:
                messages.append({"role": "assistant", "content": assistant_text, "created_at": dt})

        if messages:
            result.append(ParsedConversation(
                session_id=f"gemini_takeout_{date_key}",
                title=date_key,
                messages=messages,
            ))

    return result
