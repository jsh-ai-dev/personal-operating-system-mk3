# [서비스] OpenAI/Gemini API 호출, 대화/메시지 저장, 비용 계산을 담당하는 채팅 비즈니스 로직
# SSE(Server-Sent Events) 스트리밍으로 응답 청크를 실시간으로 프론트엔드에 전달

import json
from datetime import datetime, timezone
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


_QUIZ_SYSTEM_PROMPT = """당신은 개발자의 학습 요약을 바탕으로 4지선다 퀴즈를 만드는 전문가입니다.

배경: 사용자는 Python, FastAPI, Vue, Nuxt, Docker 등 처음 접하는 기술들을 배우고 있습니다.
나중에 다시 봤을 때 "이거 헷갈렸던 거네, 다시 확인하길 잘했다"는 문제를 만드는 것이 목표입니다.

포함 기준:
- 개념의 동작 방식, 문법, 옵션 — 처음 배우는 기술이라면 기본적인 것도 퀴즈 가치 있음
- 4개 선택지를 명확히 구분할 수 있고 정답이 딱 하나인 것
- 나중에 헷갈릴 수 있거나, 모르면 실수할 수 있는 내용

제외 기준:
- 단순 작업 지시, 코드 변경 기록, 결과물 나열 (학습 내용이 아닌 것)
- 잡담, 진행 상황 확인
- 이 프로젝트 코드를 모르면 문제 자체가 성립 안 되는 맥락 종속 내용
- 선택지를 그럴듯하게 만들기 어려운 내용 (억지로 틀린 보기를 구성해야 하는 경우)

문제 수: 제한 없음. 가치 있는 내용이 많으면 많이, 없으면 적게. 억지로 채우지 말 것.
퀴즈로 만들 내용이 없으면 {"questions": []} 반환.

출력 형식 (반드시 JSON 객체, 마크다운 코드블록 금지):
{"questions": [
  {
    "question": "질문 (한국어)",
    "options": ["A. 보기1", "B. 보기2", "C. 보기3", "D. 보기4"],
    "answer": 0,
    "explanation": "정답 해설 1~2줄 (한국어)"
  }
]}

answer는 정답 보기의 인덱스 (0~3)."""


_SUMMARIZE_SYSTEM_PROMPT = """당신은 개발자의 AI 대화를 학습 목적으로 요약하는 전문가입니다.

목표: 나중에 복습할 때 빠르게 핵심을 파악할 수 있는 요약 작성

포함 기준:
- 개념 설명, 원리 이해, 아키텍처 결정, 트레이드오프 분석
- 실무에서 반복 적용 가능한 패턴이나 모범 사례
- 처음 접한 기술·도구에 대한 설명

제외 기준:
- 단순 코드 생성·변환 (그냥 만들어 달라는 요청)
- 오탈자·문법 수정, 반복적인 단순 작업
- 결과물만 있고 배울 내용이 없는 항목

출력 형식 (반드시 준수, 한국어):
## 학습 요약

**주제 태그:** #태그1 #태그2 (3~7개, 기술·개념 키워드)

---

### [개념 제목 — 인사이트 중심 명사구]
[1~3줄. WHY와 WHEN 중심. 단순 WHAT 나열 금지]

### [다음 개념]
[1~3줄]

---
*날짜 | 모델명*

요약할 내용이 전혀 없으면: 헤더와 태그 없이 "*요약할 내용이 없습니다*" 한 줄만 출력"""


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

    async def summarize_conversation(self, conversation_id: str, model: str) -> dict:
        conversation = await self.repo.find_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError("대화를 찾을 수 없습니다")

        messages = await self.repo.find_messages_by_conversation(conversation_id)
        # 숨긴 메시지 제외 — 사용자가 의도적으로 숨긴 내용은 요약에도 포함하지 않음
        visible = [m for m in messages if not m.is_hidden]
        if not visible:
            raise ValueError("요약할 메시지가 없습니다")

        conv_text = "\n\n".join(
            f"[{'사용자' if m.role == 'user' else 'AI'}]\n{m.content}"
            for m in visible
        )
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        user_prompt = (
            f"대화 제목: {conversation.title}\n\n"
            f"아래 대화를 읽고 학습 요약을 작성해주세요.\n"
            f"각 Q&A 쌍 중 기억할 가치가 있는 내용만 요약하고, 단순 작업은 생략하세요.\n"
            f"요약 마지막 줄은 반드시 *{today} | {model}* 형식으로 끝내세요.\n\n"
            f"---\n{conv_text}"
        )

        response = await self.openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SUMMARIZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        summary_text = response.choices[0].message.content.strip()
        tokens_input = response.usage.prompt_tokens
        tokens_output = response.usage.completion_tokens
        cost_usd = _calc_cost(OPENAI_PRICING, model, tokens_input, tokens_output)

        await self.repo.update_summary(conversation_id, summary_text, model, cost_usd)

        return {
            "summary": summary_text,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "cost_usd": cost_usd,
        }

    async def generate_quiz(self, conversation_id: str, model: str) -> dict:
        conversation = await self.repo.find_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError("대화를 찾을 수 없습니다")
        if not conversation.summary:
            raise ValueError("요약이 없습니다. 먼저 요약을 생성해주세요")

        response = await self.openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _QUIZ_SYSTEM_PROMPT},
                {"role": "user", "content": f"다음 학습 요약을 바탕으로 퀴즈를 만들어주세요.\n\n{conversation.summary}"},
            ],
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content.strip()
        tokens_input = response.usage.prompt_tokens
        tokens_output = response.usage.completion_tokens
        cost_usd = _calc_cost(OPENAI_PRICING, model, tokens_input, tokens_output)

        import json as _json
        parsed = _json.loads(raw)
        # AI가 {"questions": [...]} 형태로 감쌀 수 있어서 배열만 추출
        quiz = parsed if isinstance(parsed, list) else next(
            (v for v in parsed.values() if isinstance(v, list)), []
        )

        await self.repo.update_quiz(conversation_id, quiz, model, cost_usd)

        return {
            "quiz": quiz,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "cost_usd": cost_usd,
        }

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
