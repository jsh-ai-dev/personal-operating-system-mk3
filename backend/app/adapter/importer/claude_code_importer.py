# [임포터] Claude Code 로컬 트랜스크립트 (.jsonl) 파싱해 대화 데이터 추출
# ~/.claude/projects/<cwd>/*.jsonl 파일을 backend/data/claude-code/에 복사 후 임포트
#
# JSONL 구조:
#   type: "user"      — content가 str이면 실제 질문, list이면 tool_result → 제외
#   type: "assistant" — content 블록 중 type: "text"만 추출 (thinking, tool_use 제외)

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ParsedConversation:
    session_id: str  # "claude_code_{uuid}" — 중복 임포트 방지용 고유 키
    title: str       # 첫 번째 유저 메시지 앞 50자
    messages: list[dict] = field(default_factory=list)  # [{"role", "content", "created_at"}]


def _parse_timestamp(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now()


def parse_session(path: Path) -> ParsedConversation | None:
    messages = []

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type")

            if msg_type == "user":
                content = obj.get("message", {}).get("content", "")
                # list = tool_result → 순수 텍스트 메시지만 가져옴
                if not isinstance(content, str) or not content.strip():
                    continue
                messages.append({
                    "role": "user",
                    "content": content.strip(),
                    "created_at": _parse_timestamp(obj.get("timestamp", "")),
                })

            elif msg_type == "assistant":
                text_parts = [
                    block["text"]
                    for block in obj.get("message", {}).get("content", [])
                    if block.get("type") == "text" and block.get("text", "").strip()
                ]
                text = "\n\n".join(text_parts)
                if not text:
                    continue
                messages.append({
                    "role": "assistant",
                    "content": text,
                    "created_at": _parse_timestamp(obj.get("timestamp", "")),
                })

    if not messages:
        return None

    first_user = next((m["content"] for m in messages if m["role"] == "user"), path.stem)
    title = first_user[:50] + ("..." if len(first_user) > 50 else "")

    return ParsedConversation(
        session_id=f"claude_code_{path.stem}",
        title=title,
        messages=messages,
    )


def scan_sessions(directory: str) -> list[ParsedConversation]:
    results = []
    for jsonl_file in sorted(Path(directory).glob("*.jsonl")):
        parsed = parse_session(jsonl_file)
        if parsed:
            results.append(parsed)
    return results
