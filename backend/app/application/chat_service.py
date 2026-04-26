# [서비스] OpenAI API 호출, 대화/메시지 저장, 비용 계산을 담당하는 채팅 비즈니스 로직
# SSE(Server-Sent Events) 스트리밍으로 응답 청크를 실시간으로 프론트엔드에 전달

import json
from typing import AsyncGenerator

from openai import AsyncOpenAI

from app.adapter.mongodb.conversation_repository import ConversationRepository
from app.domain.conversation import Conversation, Message

OPENAI_PRICING: dict[str, dict[str, float]] = {
    "gpt-5-nano":   {"input": 0.05,  "output": 0.40},
    "gpt-5.4-nano": {"input": 0.20,  "output": 1.25},
    "gpt-5-mini":   {"input": 0.25,  "output": 2.00},
    "gpt-5.4-mini": {"input": 0.75,  "output": 4.50},
    "gpt-5":        {"input": 1.25,  "output": 10.00},
    "gpt-5.4":      {"input": 2.50,  "output": 15.00},
}


def _calc_cost(model: str, tokens_input: int, tokens_output: int) -> float:
    pricing = OPENAI_PRICING.get(model, {"input": 0.0, "output": 0.0})
    return (tokens_input * pricing["input"] + tokens_output * pricing["output"]) / 1_000_000


class ChatService:
    def __init__(self, repo: ConversationRepository, openai_client: AsyncOpenAI):
        self.repo = repo
        self.openai = openai_client

    async def list_conversations(self) -> list[Conversation]:
        return await self.repo.find_all_conversations()

    async def get_messages(self, conversation_id: str) -> list[Message]:
        return await self.repo.find_messages_by_conversation(conversation_id)

    async def chat_openai_stream(
        self,
        conversation_id: str | None,
        model: str,
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        try:
            # 대화 생성 또는 기존 대화 로드
            if conversation_id:
                conversation = await self.repo.find_conversation_by_id(conversation_id)
                if not conversation:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Conversation not found'})}\n\n"
                    return
            else:
                title = user_message[:50] + ("..." if len(user_message) > 50 else "")
                conversation = await self.repo.create_conversation("openai", model, title)

            # 유저 메시지 저장
            await self.repo.insert_message(
                conversation_id=conversation.id,
                role="user",
                content=user_message,
            )

            # 전체 히스토리로 OpenAI 요청 구성
            history = await self.repo.find_messages_by_conversation(conversation.id)
            messages = [{"role": msg.role, "content": msg.content} for msg in history]

            # 스트리밍 호출
            full_content = ""
            tokens_input = 0
            tokens_output = 0

            stream = await self.openai.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    delta = chunk.choices[0].delta.content
                    full_content += delta
                    yield f"data: {json.dumps({'type': 'chunk', 'content': delta})}\n\n"
                if chunk.usage:
                    tokens_input = chunk.usage.prompt_tokens
                    tokens_output = chunk.usage.completion_tokens

            # 어시스턴트 메시지 저장
            cost_usd = _calc_cost(model, tokens_input, tokens_output)
            assistant_msg = await self.repo.insert_message(
                conversation_id=conversation.id,
                role="assistant",
                content=full_content,
                model=model,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                cost_usd=cost_usd,
            )

            # 대화 통계 업데이트
            await self.repo.update_conversation_stats(
                conversation.id, tokens_input, tokens_output, cost_usd
            )

            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation.id, 'message_id': assistant_msg.id, 'tokens_input': tokens_input, 'tokens_output': tokens_output, 'cost_usd': cost_usd})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
