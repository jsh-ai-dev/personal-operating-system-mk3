import json
from pathlib import Path

from app.adapter.importer.chatgpt_importer import parse_export


def test_parse_export_skips_intermediate_assistant_messages(tmp_path: Path) -> None:
    export_path = tmp_path / "conversations.json"
    export_path.write_text(
        json.dumps(
            [
                {
                    "conversation_id": "conv-1",
                    "title": "Conversation",
                    "mapping": {
                        "root": {"parent": None, "children": ["user-1"], "message": None},
                        "user-1": {
                            "parent": "root",
                            "children": ["assistant-progress"],
                            "message": {
                                "author": {"role": "user"},
                                "content": {"content_type": "text", "parts": ["question"]},
                                "create_time": 1,
                            },
                        },
                        "assistant-progress": {
                            "parent": "user-1",
                            "children": ["assistant-final"],
                            "message": {
                                "author": {"role": "assistant"},
                                "content": {"content_type": "text", "parts": ["checking..."]},
                                "create_time": 2,
                                "end_turn": False,
                            },
                        },
                        "assistant-final": {
                            "parent": "assistant-progress",
                            "children": [],
                            "message": {
                                "author": {"role": "assistant"},
                                "content": {"content_type": "text", "parts": ["answer"]},
                                "create_time": 3,
                                "end_turn": True,
                            },
                        },
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    conversations = parse_export(export_path)

    assert len(conversations) == 1
    assert [(m["role"], m["content"]) for m in conversations[0].messages] == [
        ("user", "question"),
        ("assistant", "answer"),
    ]


def test_parse_export_keeps_multimodal_user_text(tmp_path: Path) -> None:
    export_path = tmp_path / "conversations.json"
    export_path.write_text(
        json.dumps(
            [
                {
                    "conversation_id": "conv-1",
                    "title": "Conversation",
                    "mapping": {
                        "root": {"parent": None, "children": ["assistant-1"], "message": None},
                        "assistant-1": {
                            "parent": "root",
                            "children": ["user-image"],
                            "message": {
                                "author": {"role": "assistant"},
                                "content": {"content_type": "text", "parts": ["first answer"]},
                                "create_time": 1,
                                "end_turn": True,
                            },
                        },
                        "user-image": {
                            "parent": "assistant-1",
                            "children": ["assistant-2"],
                            "message": {
                                "author": {"role": "user"},
                                "content": {
                                    "content_type": "multimodal_text",
                                    "parts": [
                                        {"content_type": "image_asset_pointer", "asset_pointer": "file"},
                                        "question with screenshot",
                                    ],
                                },
                                "create_time": 2,
                            },
                        },
                        "assistant-2": {
                            "parent": "user-image",
                            "children": [],
                            "message": {
                                "author": {"role": "assistant"},
                                "content": {"content_type": "text", "parts": ["second answer"]},
                                "create_time": 3,
                                "end_turn": True,
                            },
                        },
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    conversations = parse_export(export_path)

    assert [(m["role"], m["content"]) for m in conversations[0].messages] == [
        ("assistant", "first answer"),
        ("user", "[이미지 첨부]\n\nquestion with screenshot"),
        ("assistant", "second answer"),
    ]


def test_parse_export_keeps_attachment_only_user_turn(tmp_path: Path) -> None:
    export_path = tmp_path / "conversations.json"
    export_path.write_text(
        json.dumps(
            [
                {
                    "conversation_id": "conv-1",
                    "title": "Conversation",
                    "mapping": {
                        "root": {"parent": None, "children": ["assistant-1"], "message": None},
                        "assistant-1": {
                            "parent": "root",
                            "children": ["user-attachment"],
                            "message": {
                                "author": {"role": "assistant"},
                                "content": {"content_type": "text", "parts": ["first answer"]},
                                "create_time": 1,
                                "end_turn": True,
                            },
                        },
                        "user-attachment": {
                            "parent": "assistant-1",
                            "children": ["assistant-2"],
                            "message": {
                                "author": {"role": "user"},
                                "content": {"content_type": "text", "parts": [""]},
                                "metadata": {
                                    "attachments": [
                                        {"name": "pasted text.txt", "mime_type": "text/plain"}
                                    ]
                                },
                                "create_time": 2,
                            },
                        },
                        "assistant-2": {
                            "parent": "user-attachment",
                            "children": [],
                            "message": {
                                "author": {"role": "assistant"},
                                "content": {"content_type": "text", "parts": ["second answer"]},
                                "create_time": 3,
                                "end_turn": True,
                            },
                        },
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    conversations = parse_export(export_path)

    assert [(m["role"], m["content"]) for m in conversations[0].messages] == [
        ("assistant", "first answer"),
        ("user", "[첨부 파일: pasted text.txt]"),
        ("assistant", "second answer"),
    ]


def test_parse_export_reconstructs_parent_only_mapping(tmp_path: Path) -> None:
    export_path = tmp_path / "conversations.json"
    export_path.write_text(
        json.dumps(
            [
                {
                    "conversation_id": "conv-1",
                    "current_node": "assistant-final",
                    "title": "Conversation",
                    "mapping": {
                        "root": {"parent": None, "message": None, "id": "root"},
                        "user-1": {
                            "parent": "root",
                            "id": "user-1",
                            "message": {
                                "author": {"role": "user"},
                                "content": {"content_type": "text", "parts": ["question"]},
                                "create_time": 1,
                            },
                        },
                        "assistant-progress": {
                            "parent": "user-1",
                            "id": "assistant-progress",
                            "message": {
                                "author": {"role": "assistant"},
                                "content": {"content_type": "text", "parts": ["checking..."]},
                                "create_time": 2,
                            },
                        },
                        "assistant-final": {
                            "parent": "assistant-progress",
                            "id": "assistant-final",
                            "message": {
                                "author": {"role": "assistant"},
                                "content": {"content_type": "text", "parts": ["answer"]},
                                "create_time": 3,
                            },
                        },
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    conversations = parse_export(export_path)

    assert [(m["role"], m["content"]) for m in conversations[0].messages] == [
        ("user", "question"),
        ("assistant", "answer"),
    ]
