# [임포터] ChatGPT 데이터 내보내기 conversations.json을 파싱해 대화 데이터 추출
# Settings → Data controls → Export data → 이메일로 받은 zip 파일 내 conversations.json 사용
# mapping 구조: 트리 형태로 노드 연결 — 루트에서 리프까지 순회해 메시지 순서 복원

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ChatGPT가 파일/웹 인용 시 삽입하는 내부 마커 제거 패턴
# JSON에 ... (유니코드 사용자 영역) 형태로 저장 → 앱에서 "citeturn2file0" 같은 깨진 텍스트로 표시됨
_CITATION_RE = re.compile(chr(0xE200) + '.*?' + chr(0xE201), re.DOTALL)


@dataclass
class ParsedConversation:
    session_id: str  # "chatgpt_export_{conversation_id}" — 중복 임포트 방지용 고유 키
    title: str
    messages: list[dict] = field(default_factory=list)  # [{"role", "content", "created_at"}]


def _extract_text(content: dict) -> str:
    # text 타입만 처리 — thoughts(내부 추론), code(코드 실행), reasoning_recap 등은 제외
    if content.get("content_type") != "text":
        return ""
    parts = []
    for p in content.get("parts", []):
        if not isinstance(p, str):
            continue
        cleaned = _CITATION_RE.sub('', p).strip()
        if cleaned:
            parts.append(cleaned)
    return "\n\n".join(parts)


def _traverse(mapping: dict, root_id: str) -> list[dict]:
    # 루트→리프 반복 순회 — 재귀 대신 while 루프 사용 (대화가 수백 노드일 때 RecursionError 방지)
    # 여러 자식이 있으면 마지막 자식 선택 (사용자 메시지 편집 시 생기는 분기에서 최신 흐름 추적)
    results = []
    current_id = root_id
    while current_id:
        node = mapping.get(current_id)
        if not node:
            break

        msg = node.get("message")
        if msg and msg.get("author", {}).get("role") in ("user", "assistant"):
            text = _extract_text(msg.get("content") or {})
            if text:
                ts = msg.get("create_time")
                try:
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(tz=timezone.utc)
                except (TypeError, OSError, ValueError):
                    dt = datetime.now(tz=timezone.utc)
                results.append({
                    "role": msg["author"]["role"],
                    "content": text,
                    "created_at": dt,
                })

        children = node.get("children", [])
        current_id = children[-1] if children else None

    return results


def parse_export(path: Path) -> list[ParsedConversation]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    result = []
    for conv in data:
        conv_id = conv.get("conversation_id", "")
        title = conv.get("title") or conv_id[:8]
        mapping = conv.get("mapping", {})

        # 루트 노드: parent가 None이거나 mapping에 없는 노드
        root_id = next(
            (nid for nid, node in mapping.items() if not node.get("parent") or node["parent"] not in mapping),
            None,
        )
        if not root_id:
            continue

        messages = _traverse(mapping, root_id)
        if messages:
            result.append(ParsedConversation(
                session_id=f"chatgpt_export_{conv_id}",
                title=title,
                messages=messages,
            ))

    return result
