# [서비스] 대화 임베딩 생성 및 의미 기반 검색을 담당하는 비즈니스 로직
# OpenAI 임베딩 모델로 텍스트를 벡터화하고, Qdrant에 저장·검색하는 RAG 검색 레이어

import logging

from openai import AsyncOpenAI

from app.adapter.mongodb.conversation_repository import ConversationRepository
from app.adapter.qdrant.vector_repository import VectorRepository

logger = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-3-small"
# 임베딩에 넣을 텍스트 최대 길이 — 너무 길면 토큰 초과, 너무 짧으면 검색 품질 저하
_EMBED_CHAR_BUDGET = 3000
# text-embedding-3-small 공식 가격 (2025년 기준)
_EMBED_PRICE_PER_1M = 0.02


def _calc_embed_cost(tokens: int) -> float:
    return round(tokens * _EMBED_PRICE_PER_1M / 1_000_000, 8)


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

        return {
            "results": [
                {
                    "conversation_id": p.payload["conversation_id"],
                    "title": p.payload["title"],
                    "model": p.payload["model"],
                    "created_at": p.payload["created_at"],
                    "score": round(p.score, 4),
                }
                for p in points
            ],
            "cost_usd": cost_usd,
        }
