# [임포터] Claude.ai 데이터 내보내기 conversations.json을 파싱해 대화 데이터 추출
# 설정 > 개인정보보호 > 데이터 내보내기로 받은 파일 사용

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ParsedConversation:
    session_id: str  # "claude_export_{uuid}" — 중복 임포트 방지용 고유 키
    title: str
    messages: list[dict] = field(default_factory=list)  # [{"role", "content", "created_at"}]


def _extract_text(msg: dict) -> str:
    # 최상위 text 필드 우선 사용
    text = msg.get("text", "").strip()
    if text:
        return text
    # 없으면 content 블록에서 text 타입만 수집 (thinking, tool_use 제외)
    parts = [
        block["text"]
        for block in msg.get("content", [])
        if block.get("type") == "text" and block.get("text", "").strip()
    ]
    return "\n\n".join(parts)


def parse_export(path: Path) -> list[ParsedConversation]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    result = []
    for conv in data:
        conv_uuid = conv.get("uuid", "")
        title = conv.get("name") or conv_uuid[:8]

        messages = []
        for msg in conv.get("chat_messages", []):
            sender = msg.get("sender", "")
            if sender not in ("human", "assistant"):
                continue

            text = _extract_text(msg)
            if not text:
                continue

            # created_at 파싱 — 메시지 순서 보존용
            created_at_str = msg.get("created_at", "")
            try:
                dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.now()

            messages.append({
                "role": "user" if sender == "human" else "assistant",
                "content": text,
                "created_at": dt,
            })

        if messages:
            result.append(ParsedConversation(
                session_id=f"claude_export_{conv_uuid}",
                title=title,
                messages=messages,
            ))

    return result
