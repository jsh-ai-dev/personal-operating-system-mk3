# [서비스] OpenAI/Gemini API 호출, 대화/메시지 저장, 비용 계산을 담당하는 채팅 비즈니스 로직
# SSE(Server-Sent Events) 스트리밍으로 응답 청크를 실시간으로 프론트엔드에 전달

import json
from typing import AsyncGenerator

import anthropic as anthropic_sdk
from google import genai as google_genai
from openai import AsyncOpenAI

from app.adapter.mongodb.conversation_repository import ConversationRepository
from app.domain.conversation import Conversation, Message

CLAUDE_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-7":   {"input": 5.00,  "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5":  {"input": 1.00,  "output": 5.00},
}

OPENAI_PRICING: dict[str, dict[str, float]] = {
    "gpt-5-nano":   {"input": 0.05,  "output": 0.40},
    "gpt-5.4-nano": {"input": 0.20,  "output": 1.25},
    "gpt-5-mini":   {"input": 0.25,  "output": 2.00},
    "gpt-5.4-mini": {"input": 0.75,  "output": 4.50},
    "gpt-5":        {"input": 1.25,  "output": 10.00},
    "gpt-5.4":      {"input": 2.50,  "output": 15.00},
}

# 무료 티어 사용 — 비용 대신 rate limit으로 관리
# cost_usd 계산 시 0으로 처리
GEMINI_PRICING: dict[str, dict[str, float]] = {
    "gemini-2.5-flash-lite":         {"input": 0.0, "output": 0.0},
    "gemini-2.5-flash":              {"input": 0.0, "output": 0.0},
    "gemini-2.5-pro":                {"input": 0.0, "output": 0.0},
    "gemini-3.1-flash-lite-preview": {"input": 0.0, "output": 0.0},
    "gemini-3.1-flash-preview":      {"input": 0.0, "output": 0.0},
    "gemini-3.1-pro-preview":        {"input": 0.0, "output": 0.0},
}

# 무료 티어 rate limit (rpm: 분당 요청, rpd: 일일 요청, tpm: 분당 토큰)
GEMINI_LIMITS: dict[str, dict[str, int]] = {
    "gemini-2.5-flash-lite":         {"rpm": 30, "rpd": 2000, "tpm": 1_000_000},
    "gemini-2.5-flash":              {"rpm": 15, "rpd": 1500, "tpm": 1_000_000},
    "gemini-2.5-pro":                {"rpm": 5,  "rpd": 100,  "tpm": 250_000},
    "gemini-3.1-flash-lite-preview": {"rpm": 30, "rpd": 1500, "tpm": 500_000},
    "gemini-3.1-flash-preview":      {"rpm": 15, "rpd": 1000, "tpm": 250_000},
    "gemini-3.1-pro-preview":        {"rpm": 2,  "rpd": 50,   "tpm": 250_000},
}


def _calc_cost(pricing_table: dict, model: str, tokens_input: int, tokens_output: int) -> float:
    pricing = pricing_table.get(model, {"input": 0.0, "output": 0.0})
    return (tokens_input * pricing["input"] + tokens_output * pricing["output"]) / 1_000_000


class ChatService:
    def __init__(self, repo: ConversationRepository, openai_client: AsyncOpenAI):
        self.repo = repo
        self.openai = openai_client

    async def list_conversations(self, include_hidden: bool = False) -> list[Conversation]:
        return await self.repo.find_all_conversations(include_hidden=include_hidden)

    async def get_messages(self, conversation_id: str) -> list[Message]:
        return await self.repo.find_messages_by_conversation(conversation_id)

    async def set_hidden(self, conversation_id: str, is_hidden: bool) -> None:
        await self.repo.set_hidden(conversation_id, is_hidden)

    async def set_message_hidden(self, message_id: str, is_hidden: bool) -> None:
        await self.repo.set_message_hidden(message_id, is_hidden)

    async def update_message_content(self, message_id: str, content: str) -> None:
        await self.repo.update_message_content(message_id, content)

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
            cost_usd = _calc_cost(OPENAI_PRICING, model, tokens_input, tokens_output)
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

    async def chat_gemini_stream(
        self,
        conversation_id: str | None,
        model: str,
        user_message: str,
        gemini_api_key: str,
    ) -> AsyncGenerator[str, None]:
        try:
            if conversation_id:
                conversation = await self.repo.find_conversation_by_id(conversation_id)
                if not conversation:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Conversation not found'})}\n\n"
                    return
            else:
                title = user_message[:50] + ("..." if len(user_message) > 50 else "")
                conversation = await self.repo.create_conversation("google", model, title)

            await self.repo.insert_message(
                conversation_id=conversation.id,
                role="user",
                content=user_message,
            )

            # Gemini는 role이 "user"/"model" — "assistant"를 "model"로 변환
            history = await self.repo.find_messages_by_conversation(conversation.id)
            contents = [
                {"role": "model" if msg.role == "assistant" else "user",
                 "parts": [{"text": msg.content}]}
                for msg in history
            ]

            client = google_genai.Client(api_key=gemini_api_key)
            full_content = ""
            tokens_input = 0
            tokens_output = 0

            async for chunk in await client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
            ):
                if chunk.text:
                    full_content += chunk.text
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk.text})}\n\n"
                # 마지막 청크에 usage_metadata 포함
                if chunk.usage_metadata:
                    tokens_input = chunk.usage_metadata.prompt_token_count or 0
                    tokens_output = chunk.usage_metadata.candidates_token_count or 0

            cost_usd = _calc_cost(GEMINI_PRICING, model, tokens_input, tokens_output)
            assistant_msg = await self.repo.insert_message(
                conversation_id=conversation.id,
                role="assistant",
                content=full_content,
                model=model,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                cost_usd=cost_usd,
            )

            await self.repo.update_conversation_stats(
                conversation.id, tokens_input, tokens_output, cost_usd
            )

            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation.id, 'message_id': assistant_msg.id, 'tokens_input': tokens_input, 'tokens_output': tokens_output, 'cost_usd': cost_usd})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    async def chat_claude_stream(
        self,
        conversation_id: str | None,
        model: str,
        user_message: str,
        anthropic_api_key: str,
    ) -> AsyncGenerator[str, None]:
        try:
            if conversation_id:
                conversation = await self.repo.find_conversation_by_id(conversation_id)
                if not conversation:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Conversation not found'})}\n\n"
                    return
            else:
                title = user_message[:50] + ("..." if len(user_message) > 50 else "")
                conversation = await self.repo.create_conversation("anthropic", model, title)

            await self.repo.insert_message(
                conversation_id=conversation.id,
                role="user",
                content=user_message,
            )

            # Anthropic은 role이 OpenAI와 동일 ("user"/"assistant") — 변환 불필요
            history = await self.repo.find_messages_by_conversation(conversation.id)
            messages = [{"role": msg.role, "content": msg.content} for msg in history]

            client = anthropic_sdk.AsyncAnthropic(api_key=anthropic_api_key)
            full_content = ""
            tokens_input = 0
            tokens_output = 0

            async with client.messages.stream(
                model=model,
                max_tokens=8096,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    full_content += text
                    yield f"data: {json.dumps({'type': 'chunk', 'content': text})}\n\n"
                final = await stream.get_final_message()
                tokens_input = final.usage.input_tokens
                tokens_output = final.usage.output_tokens

            cost_usd = _calc_cost(CLAUDE_PRICING, model, tokens_input, tokens_output)
            assistant_msg = await self.repo.insert_message(
                conversation_id=conversation.id,
                role="assistant",
                content=full_content,
                model=model,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                cost_usd=cost_usd,
            )

            await self.repo.update_conversation_stats(
                conversation.id, tokens_input, tokens_output, cost_usd
            )

            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation.id, 'message_id': assistant_msg.id, 'tokens_input': tokens_input, 'tokens_output': tokens_output, 'cost_usd': cost_usd})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
