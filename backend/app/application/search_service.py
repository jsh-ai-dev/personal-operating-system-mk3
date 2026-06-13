# [서비스] 대화 임베딩 생성 및 의미 기반 검색을 담당하는 비즈니스 로직
# OpenAI 임베딩 모델로 텍스트를 벡터화하고, Qdrant에 저장·검색하는 RAG 검색 레이어

import logging

from openai import AsyncOpenAI

from app.adapter.mongodb.conversation_repository import ConversationRepository
from app.adapter.qdrant.vector_repository import VectorRepository
from app.application.chat_service import OPENAI_PRICING, _calc_cost

logger = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-3-small"
RAG_ANSWER_MODEL = "gpt-5-mini"
RAG_MAX_SOURCES = 5
RAG_MIN_SCORE = 0.3
# 임베딩에 넣을 텍스트 최대 길이 — 너무 길면 토큰 초과, 너무 짧으면 검색 품질 저하
_EMBED_CHAR_BUDGET = 3000
_SUMMARY_EXCERPT_CHARS = 180
# text-embedding-3-small 공식 가격 (2025년 기준)
_EMBED_PRICE_PER_1M = 0.02
_RAG_SYSTEM_PROMPT = """당신은 사용자의 과거 AI 대화 요약만 근거로 답변하는 검색 보조자입니다.

규칙:
- 제공된 출처 요약에 있는 내용만 사용하세요.
- 출처에 없는 사실을 추측하거나 일반 지식으로 보완하지 마세요.
- 제공된 출처만으로 답할 수 없으면 근거가 부족하다고 말하고, 더 구체적인 검색어 또는 관련 대화 요약이 필요하다고 안내하세요.
- 한국어로 답변하세요."""
_INSUFFICIENT_GROUNDING_MESSAGE = "관련 요약 대화가 부족합니다. 먼저 관련 대화를 요약하거나 검색어를 구체화하세요."


def _calc_embed_cost(tokens: int) -> float:
    return round(tokens * _EMBED_PRICE_PER_1M / 1_000_000, 8)


def _normalize_limit(limit: int) -> int:
    return max(1, min(limit, RAG_MAX_SOURCES))


def _summary_excerpt(summary: str) -> str:
    normalized = " ".join(summary.split())
    if len(normalized) <= _SUMMARY_EXCERPT_CHARS:
        return normalized
    return f"{normalized[:_SUMMARY_EXCERPT_CHARS].rstrip()}..."


class SearchService:
    def __init__(self, conv_repo: ConversationRepository, vector_repo: VectorRepository, openai: AsyncOpenAI):
        self.conv_repo = conv_repo
        self.vector_repo = vector_repo
        self.openai = openai

    async def embed_conversation(self, conversation_id: str, owner_id: str) -> float:
        """대화 한 건을 임베딩해서 Qdrant에 저장한다. 소모된 비용(USD)을 반환한다."""
        conv = await self.conv_repo.find_conversation_by_id(conversation_id, owner_id)
        if not conv:
            return 0.0

        if conv.summary:
            # 요약이 있으면 요약 사용 — 핵심만 추려진 텍스트라 같은 예산에서 의미 밀도가 높음
            text = f"{conv.title}\n\n{conv.summary}"
        else:
            # 요약 없으면 메시지 원문을 예산 내에서 이어 붙임
            messages = await self.conv_repo.find_messages_by_conversation(conversation_id, owner_id)
            parts = [conv.title]
            budget = _EMBED_CHAR_BUDGET
            for msg in messages:
                if budget <= 0:
                    break
                snippet = msg.content[:budget]
                parts.append(f"[{msg.role}] {snippet}")
                budget -= len(snippet)
            text = "\n".join(parts)

        resp = await self.openai.embeddings.create(model=EMBED_MODEL, input=text)
        vector = resp.data[0].embedding
        cost_usd = _calc_embed_cost(resp.usage.total_tokens)

        await self.vector_repo.ensure_collection()
        point_id = await self.vector_repo.upsert(
            conversation_id=conversation_id,
            vector=vector,
            payload={
                "conversation_id": conversation_id,
                "owner_id": owner_id,
                "title": conv.title,
                "model": conv.model,
                "created_at": conv.created_at,
            },
        )
        # 임베딩 완료 후 MongoDB에 point ID 저장 → index_all 재실행 시 중복 임베딩 방지
        await self.conv_repo.update_qdrant_id(conversation_id, owner_id, point_id)
        return cost_usd

    async def index_all(self, owner_id: str) -> dict:
        """qdrant_id가 없는 대화만 임베딩한다. 이미 인덱싱된 대화는 건너뜀."""
        conversations = await self.conv_repo.find_all_conversations(owner_id=owner_id, include_hidden=True)
        indexed = 0
        skipped = 0
        failed = 0
        total_cost_usd = 0.0
        for conv in conversations:
            if conv.qdrant_id:
                skipped += 1
                continue
            try:
                cost = await self.embed_conversation(conv.id, owner_id)
                total_cost_usd += cost
                indexed += 1
            except Exception as e:
                logger.warning("embed failed for %s: %s", conv.id, e)
                failed += 1
        return {
            "indexed": indexed,
            "skipped": skipped,
            "failed": failed,
            "total": len(conversations),
            "cost_usd": round(total_cost_usd, 6),
        }

    async def search(self, query: str, owner_id: str, limit: int = 10) -> dict:
        """질의어를 임베딩해서 코사인 유사도 기준 상위 N개 대화를 반환한다."""
        resp = await self.openai.embeddings.create(model=EMBED_MODEL, input=query)
        vector = resp.data[0].embedding
        cost_usd = _calc_embed_cost(resp.usage.total_tokens)

        await self.vector_repo.ensure_collection()
        points = await self.vector_repo.search(vector, owner_id, limit)

        # Qdrant payload에 없는 필드(provider, summary 여부, message_count 등)를 MongoDB에서 한 번에 보강
        conv_ids = [p.payload["conversation_id"] for p in points]
        conv_map = await self.conv_repo.find_conversations_by_ids(conv_ids, owner_id)

        results = []
        for p in points:
            cid = p.payload["conversation_id"]
            conv = conv_map.get(cid)
            results.append({
                "conversation_id": cid,
                "title": p.payload["title"],
                "model": p.payload["model"],
                "provider": conv.provider if conv else "",
                "summary": bool(conv.summary) if conv else False,
                "message_count": conv.message_count if conv else 0,
                "total_cost_usd": conv.total_cost_usd if conv else 0.0,
                "created_at": p.payload["created_at"],
                "score": round(p.score, 4),
            })

        return {"results": results, "cost_usd": cost_usd}

    async def answer(self, query: str, owner_id: str, limit: int = RAG_MAX_SOURCES) -> dict:
        """검색된 요약 대화를 근거로 답변을 생성한다. 원문 메시지는 답변 근거로 사용하지 않는다."""
        trimmed_query = query.strip()
        if not trimmed_query:
            raise ValueError("검색어를 입력해주세요")

        source_limit = _normalize_limit(limit)
        resp = await self.openai.embeddings.create(model=EMBED_MODEL, input=trimmed_query)
        vector = resp.data[0].embedding
        search_cost_usd = _calc_embed_cost(resp.usage.total_tokens)

        source_point_ids = await self.conv_repo.find_rag_source_qdrant_ids(owner_id)
        if not source_point_ids:
            return {
                "status": "insufficient_grounding",
                "answer": "",
                "sources": [],
                "model": RAG_ANSWER_MODEL,
                "tokens_input": 0,
                "tokens_output": 0,
                "cost_usd": 0.0,
                "search_cost_usd": search_cost_usd,
                "message": _INSUFFICIENT_GROUNDING_MESSAGE,
            }

        await self.vector_repo.ensure_collection()
        points = await self.vector_repo.search(vector, owner_id, source_limit, point_ids=source_point_ids)

        conv_ids = [p.payload["conversation_id"] for p in points]
        conv_map = await self.conv_repo.find_conversations_by_ids(conv_ids, owner_id)

        sources = []
        prompt_sources = []
        seen = set()
        for p in points:
            cid = p.payload["conversation_id"]
            if cid in seen:
                continue
            seen.add(cid)
            if len(sources) >= source_limit:
                break
            if p.score < RAG_MIN_SCORE:
                continue

            conv = conv_map.get(cid)
            if not conv or conv.is_hidden or not conv.summary:
                continue

            source = {
                "conversation_id": cid,
                "title": conv.title or p.payload.get("title", "(untitled)"),
                "summary_excerpt": _summary_excerpt(conv.summary),
                "created_at": conv.created_at or p.payload.get("created_at", ""),
                "provider": conv.provider,
                "model": conv.model,
                "score": round(p.score, 4),
                "href": f"/mk3/chat/{cid}",
            }
            sources.append(source)
            prompt_sources.append(
                "\n".join(
                    [
                        f"[출처 {len(sources)}]",
                        f"제목: {source['title']}",
                        f"대화 ID: {cid}",
                        f"생성일: {source['created_at']}",
                        f"유사도: {source['score']}",
                        f"요약: {conv.summary}",
                    ]
                )
            )

        if not sources:
            return {
                "status": "insufficient_grounding",
                "answer": "",
                "sources": [],
                "model": RAG_ANSWER_MODEL,
                "tokens_input": 0,
                "tokens_output": 0,
                "cost_usd": 0.0,
                "search_cost_usd": search_cost_usd,
                "message": _INSUFFICIENT_GROUNDING_MESSAGE,
            }

        user_prompt = (
            f"질문: {trimmed_query}\n\n"
            "아래 출처 요약만 근거로 답변하세요.\n\n"
            f"{'\n\n'.join(prompt_sources)}"
        )
        response = await self.openai.chat.completions.create(
            model=RAG_ANSWER_MODEL,
            messages=[
                {"role": "system", "content": _RAG_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        answer = response.choices[0].message.content.strip()
        tokens_input = response.usage.prompt_tokens
        tokens_output = response.usage.completion_tokens
        cost_usd = round(_calc_cost(OPENAI_PRICING, RAG_ANSWER_MODEL, tokens_input, tokens_output), 8)

        return {
            "status": "answered",
            "answer": answer,
            "sources": sources,
            "model": RAG_ANSWER_MODEL,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "cost_usd": cost_usd,
            "search_cost_usd": search_cost_usd,
            "message": "",
        }
