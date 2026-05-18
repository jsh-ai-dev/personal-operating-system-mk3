import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.application.import_service import ImportService, ImportUploadRequired


class FakeS3:
    def __init__(self, payload: list[dict]):
        self.payload = payload
        self.downloaded_keys: list[str] = []

    async def download_file(self, key: str, dest: Path) -> None:
        self.downloaded_keys.append(key)
        dest.write_text(json.dumps(self.payload), encoding="utf-8")


class FakeRepo:
    def __init__(self, upload: dict | None):
        self.upload = upload
        self.messages: list[dict] = []
        self.marked: tuple[str, str, str] | None = None

    async def find_import_upload(self, owner_id: str, service: str, upload_id: str) -> dict | None:
        if self.upload and self.upload["owner_id"] == owner_id and self.upload["service"] == service:
            return self.upload if self.upload["upload_id"] == upload_id else None
        return None

    async def mark_import_upload_imported(self, owner_id: str, service: str, upload_id: str) -> None:
        self.marked = (owner_id, service, upload_id)

    async def find_conversation_by_source_id(self, source_id: str, owner_id: str):
        return None

    async def create_conversation(self, **kwargs):
        return SimpleNamespace(id="conversation-db-id")

    async def insert_message(self, **kwargs):
        self.messages.append(kwargs)

    async def set_message_count(self, id: str, owner_id: str, count: int) -> None:
        self.message_count = count

    async def upsert_import_history(self, service: str, owner_id: str, imported_count: int) -> None:
        self.import_history = (service, owner_id, imported_count)


def _chatgpt_export_payload() -> list[dict]:
    return [
        {
            "conversation_id": "conv-1",
            "title": "Conversation",
            "mapping": {
                "root": {"parent": None, "children": ["user-1"], "message": None},
                "user-1": {
                    "parent": "root",
                    "children": ["assistant-1"],
                    "message": {
                        "author": {"role": "user"},
                        "content": {"content_type": "text", "parts": ["question"]},
                        "create_time": 1,
                    },
                },
                "assistant-1": {
                    "parent": "user-1",
                    "children": [],
                    "message": {
                        "author": {"role": "assistant"},
                        "content": {"content_type": "text", "parts": ["answer"]},
                        "create_time": 2,
                        "end_turn": True,
                    },
                },
            },
        }
    ]


def test_s3_import_requires_upload_id() -> None:
    svc = ImportService(FakeRepo(upload=None), s3=FakeS3(_chatgpt_export_payload()))

    with pytest.raises(ImportUploadRequired):
        asyncio.run(svc.import_chatgpt_export("user-1", "unused-local-path"))


def test_s3_import_uses_user_scoped_upload_prefix() -> None:
    upload = {"owner_id": "user/1", "service": "chatgpt-export", "upload_id": "upload123"}
    repo = FakeRepo(upload=upload)
    s3 = FakeS3(_chatgpt_export_payload())
    svc = ImportService(repo, s3=s3)

    result = asyncio.run(svc.import_chatgpt_export("user/1", "unused-local-path", upload_id="upload123"))

    assert result == {"imported": 1, "skipped": 0, "total": 1}
    assert s3.downloaded_keys == ["imports/user%2F1/upload123/chatgpt/conversations.json"]
    assert [m["content"] for m in repo.messages] == ["question", "answer"]
    assert repo.marked == ("user/1", "chatgpt-export", "upload123")
