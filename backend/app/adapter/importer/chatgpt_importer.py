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
    # text/multimodal_text만 처리 — thoughts(내부 추론), code, reasoning_recap 등은 제외
    if content.get("content_type") not in ("text", "multimodal_text"):
        return ""
    parts = []
    for p in content.get("parts", []):
        if isinstance(p, dict):
            if p.get("content_type") == "image_asset_pointer":
                parts.append("[이미지 첨부]")
            continue
        if not isinstance(p, str):
            continue
        cleaned = _CITATION_RE.sub('', p).strip()
        if cleaned:
            parts.append(cleaned)
    return "\n\n".join(parts)


def _extract_attachment_text(msg: dict) -> str:
    attachments = msg.get("metadata", {}).get("attachments", [])
    if not attachments:
        return ""

    labels = []
    for attachment in attachments:
        name = attachment.get("name") or "첨부 파일"
        labels.append(f"[첨부 파일: {name}]")
    return "\n\n".join(labels)


def _should_include_message(msg: dict) -> bool:
    role = msg.get("author", {}).get("role")
    if role == "user":
        return True
    if role == "assistant":
        # ChatGPT export can contain assistant progress/status messages in the
        # same turn before the final answer. Only the final assistant message
        # has end_turn=True and should become a stored conversation message.
        return msg.get("end_turn") is True
    return False


def _active_path_ids(mapping: dict, root_id: str, current_node: str | None) -> list[str]:
    # 최신 export는 children을 생략하고 parent + current_node만 제공한다.
    # 이 경우 leaf에서 parent를 따라 올라간 뒤 뒤집어 활성 대화 경로를 복원한다.
    if current_node and current_node in mapping and not mapping.get(root_id, {}).get("children"):
        path = []
        seen = set()
        current_id = current_node
        while current_id and current_id in mapping and current_id not in seen:
            seen.add(current_id)
            path.append(current_id)
            current_id = mapping[current_id].get("parent")
        path.reverse()
        return path

    # 구 export는 children을 제공한다. 여러 자식이 있으면 마지막 자식을 선택해 최신 분기를 따른다.
    path = []
    current_id = root_id
    while current_id:
        node = mapping.get(current_id)
        if not node:
            break
        path.append(current_id)
        children = node.get("children", [])
        current_id = children[-1] if children else None
    return path


def _to_parsed_message(msg: dict, text: str) -> dict:
    ts = msg.get("create_time")
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(tz=timezone.utc)
    except (TypeError, OSError, ValueError):
        dt = datetime.now(tz=timezone.utc)
    return {
        "role": msg["author"]["role"],
        "content": text,
        "created_at": dt,
    }


def _traverse(mapping: dict, root_id: str, current_node: str | None = None) -> list[dict]:
    results = []
    pending_assistant: dict | None = None

    def flush_assistant() -> None:
        nonlocal pending_assistant
        if pending_assistant:
            results.append(pending_assistant)
            pending_assistant = None

    for node_id in _active_path_ids(mapping, root_id, current_node):
        msg = mapping[node_id].get("message")
        if not msg:
            continue

        role = msg.get("author", {}).get("role")
        if role == "user":
            flush_assistant()
            text = _extract_text(msg.get("content") or {}) or _extract_attachment_text(msg)
            if text:
                results.append(_to_parsed_message(msg, text))
            continue

        if role != "assistant":
            continue

        text = _extract_text(msg.get("content") or {})
        if not text:
            continue

        # 구 export는 end_turn으로 최종 답변을 표시한다. 최신 export는 end_turn이
        # 없으므로 같은 user 턴 안에서 마지막 assistant 텍스트만 최종 답변으로 본다.
        if "end_turn" in msg and not _should_include_message(msg):
            continue
        pending_assistant = _to_parsed_message(msg, text)

    flush_assistant()

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

        messages = _traverse(mapping, root_id, conv.get("current_node"))
        if messages:
            result.append(ParsedConversation(
                session_id=f"chatgpt_export_{conv_id}",
                title=title,
                messages=messages,
            ))

    return result
