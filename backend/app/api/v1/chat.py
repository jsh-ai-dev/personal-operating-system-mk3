# [API] ChatGPT(OpenAI) 채팅 관련 HTTP 엔드포인트
# /chat 접두사로 대화 목록 조회, 메시지 조회, 모델 목록, SSE 스트리밍 채팅을 제공

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.adapter.mongodb.conversation_repository import ConversationRepository
from app.application.chat_service import OPENAI_PRICING, ChatService
from app.core.config import settings
from app.core.dependencies import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


def _get_svc(db: AsyncIOMotorDatabase = Depends(get_db)) -> ChatService:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    return ChatService(ConversationRepository(db), client)


class OpenAIChatRequest(BaseModel):
    conversation_id: str | None = None
    model: str = "gpt-4o-mini"
    message: str


class UpdateConversationRequest(BaseModel):
    is_hidden: bool


class UpdateMessageRequest(BaseModel):
    is_hidden: bool | None = None
    content: str | None = None


@router.get("/conversations")
async def list_conversations(include_hidden: bool = False, svc: ChatService = Depends(_get_svc)):
    convs = await svc.list_conversations(include_hidden=include_hidden)
    return [asdict(c) for c in convs]


@router.patch("/conversations/{id}")
async def update_conversation(
    id: str, body: UpdateConversationRequest, svc: ChatService = Depends(_get_svc)
):
    await svc.set_hidden(id, body.is_hidden)
    return {"ok": True}


@router.patch("/messages/{id}")
async def update_message(
    id: str, body: UpdateMessageRequest, svc: ChatService = Depends(_get_svc)
):
    if body.is_hidden is not None:
        await svc.set_message_hidden(id, body.is_hidden)
    if body.content is not None:
        await svc.update_message_content(id, body.content)
    return {"ok": True}


@router.get("/conversations/{id}/messages")
async def get_messages(id: str, svc: ChatService = Depends(_get_svc)):
    msgs = await svc.get_messages(id)
    return [asdict(m) for m in msgs]


@router.get("/openai/models")
async def get_openai_models():
    models = [
        {"id": model_id, "input_per_1m": p["input"], "output_per_1m": p["output"]}
        for model_id, p in OPENAI_PRICING.items()
    ]
    return sorted(models, key=lambda m: m["input_per_1m"])


@router.post("/openai")
async def chat_openai(body: OpenAIChatRequest, svc: ChatService = Depends(_get_svc)):
    if body.model not in OPENAI_PRICING:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 모델: {body.model}")
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY가 설정되지 않았습니다")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="메시지를 입력해주세요")

    return StreamingResponse(
        svc.chat_openai_stream(body.conversation_id, body.model, body.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
