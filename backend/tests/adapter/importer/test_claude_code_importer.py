import json
from pathlib import Path

from app.adapter.importer.claude_code_importer import parse_session


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row) for row in rows),
        encoding="utf-8",
    )


def test_parse_session_extracts_new_user_text_blocks(tmp_path: Path) -> None:
    session_path = tmp_path / "session-1.jsonl"
    _write_jsonl(
        session_path,
        [
            {
                "type": "user",
                "message": {
                    "content": [
                        {"type": "text", "text": "First question"},
                        {"type": "text", "text": "with more context"},
                    ]
                },
                "timestamp": "2026-05-13T00:00:00Z",
            },
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Answer"}]},
                "timestamp": "2026-05-13T00:00:01Z",
            },
            {
                "type": "user",
                "message": {
                    "content": [
                        {"type": "tool_result", "content": "command output", "tool_use_id": "tool-1"}
                    ]
                },
                "timestamp": "2026-05-13T00:00:02Z",
            },
        ],
    )

    conversation = parse_session(session_path)

    assert conversation is not None
    assert [(m["role"], m["content"]) for m in conversation.messages] == [
        ("user", "First question\n\nwith more context"),
        ("assistant", "Answer"),
    ]


def test_parse_session_keeps_legacy_user_string_content(tmp_path: Path) -> None:
    session_path = tmp_path / "session-legacy.jsonl"
    _write_jsonl(
        session_path,
        [
            {
                "type": "user",
                "message": {"content": "Legacy question"},
                "timestamp": "2026-05-10T00:00:00Z",
            }
        ],
    )

    conversation = parse_session(session_path)

    assert conversation is not None
    assert [(m["role"], m["content"]) for m in conversation.messages] == [
        ("user", "Legacy question"),
    ]
