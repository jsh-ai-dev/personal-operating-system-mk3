# [임포터] JetBrains AI Assistant(Codex) .events 파일을 파싱해 대화 데이터를 추출
# AUI_EVENTS_V1 포맷: 헤더 + base64 인코딩된 JSON 이벤트를 한 줄씩 저장
#
# 파일 위치: {jetbrains_config}/aia-task-history/{uuid}.events
# 이벤트 타입:
#   - ChatSessionUserPromptEvent       : 유저 메시지
#   - MarkdownBlockUpdatedEvent        : AI 텍스트 응답 (같은 stepId가 여러 번 오면 스트리밍 중간 청크 → 마지막 것이 완성본)
#   - TerminalBlockUpdatedEvent        : Codex가 실행한 명령어 (대화 내용 아님, 무시)

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ParsedConversation:
    session_id: str               # 파일명(UUID) — source_id로 저장해 중복 임포트 방지
    title: str
    messages: list[dict] = field(default_factory=list)  # [{"role": "user"|"assistant", "content": str}]
    created_at: datetime | None = None  # .events 파일 수정 시간 — 이벤트에 타임스탬프가 없어 근사치로 사용


def parse_events_file(path: Path) -> ParsedConversation | None:
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    if not lines or lines[0].strip() != "AUI_EVENTS_V1":
        return None

    events = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(base64.b64decode(line)))
        except Exception:
            continue

    if not events:
        return None

    result = _reconstruct_conversation(path.stem, events)
    if result:
        # 이벤트에 타임스탬프 필드가 없으므로 파일 수정 시간을 근사치로 사용
        result.created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return result


def _reconstruct_conversation(session_id: str, events: list[dict]) -> ParsedConversation | None:
    # Pass 1: stepId별로 마지막(완성된) 마크다운 텍스트 수집
    # 스트리밍 방식이라 같은 stepId로 여러 이벤트가 오고, 마지막 이벤트가 전체 텍스트
    markdown_final: dict[str, str] = {}   # stepId -> 최종 텍스트
    markdown_first_evt: dict[str, int] = {}  # stepId -> 첫 등장 event_id (순서 보존용)

    for evt in events:
        evt_id = evt.get("id", {}).get("id", 0)
        inner = evt.get("event", {})
        if "MarkdownBlockUpdatedEvent" in inner.get("kind", ""):
            step_id = inner.get("stepId", "")
            markdown_final[step_id] = inner.get("text", "")
            if step_id not in markdown_first_evt:
                markdown_first_evt[step_id] = evt_id

    # Pass 2: 유저 메시지 기준으로 턴(turn) 구성
    # 턴 = UserPromptEvent 하나 + 그 다음 UserPromptEvent 전까지의 MarkdownBlock들
    turns: list[tuple[str, list[str]]] = []  # [(user_content, [step_id, ...])]
    current_user: str | None = None
    current_step_ids: list[str] = []

    for evt in events:
        evt_type = evt.get("type", "")

        if "UserPromptEvent" in evt_type:
            if current_user is not None:
                turns.append((current_user, current_step_ids))
            current_user = evt.get("prompt", "")
            current_step_ids = []

        elif "MessageBlockEvent" in evt_type:
            inner = evt.get("event", {})
            if "MarkdownBlockUpdatedEvent" in inner.get("kind", ""):
                step_id = inner.get("stepId", "")
                # 같은 stepId는 첫 등장 위치에서만 추가 (중복 방지)
                if step_id not in current_step_ids:
                    current_step_ids.append(step_id)

    if current_user is not None:
        turns.append((current_user, current_step_ids))

    if not turns:
        return None

    messages = []
    for user_content, step_ids in turns:
        if user_content.strip():
            messages.append({"role": "user", "content": user_content})

        assistant_parts = [
            markdown_final[sid]
            for sid in step_ids
            if sid in markdown_final and markdown_final[sid].strip()
        ]
        if assistant_parts:
            messages.append({"role": "assistant", "content": "\n\n".join(assistant_parts)})

    if not messages:
        return None

    first_user = turns[0][0]
    title = first_user[:50] + ("..." if len(first_user) > 50 else "")
    return ParsedConversation(session_id=session_id, title=title, messages=messages)


def scan_sessions(aia_path: str) -> list[ParsedConversation]:
    """aia-task-history 디렉토리의 모든 .events 파일을 파싱해 반환"""
    results = []
    for events_file in Path(aia_path).glob("*.events"):
        parsed = parse_events_file(events_file)
        if parsed:
            results.append(parsed)
    return results
