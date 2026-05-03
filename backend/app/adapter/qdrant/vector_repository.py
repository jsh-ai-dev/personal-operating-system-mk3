# [어댑터] Qdrant 벡터 DB에 대한 CRUD 연산을 담당하는 저장소 구현체
# 대화를 임베딩 벡터로 변환한 뒤 저장/검색하는 의미 검색의 핵심 인프라 레이어

import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)

COLLECTION = "conversations"
VECTOR_SIZE = 1536  # text-embedding-3-small 출력 차원


def _point_id(conversation_id: str) -> str:
    # Qdrant point ID는 UUID 형식이어야 함 — MongoDB ObjectId(24자 hex)를 결정론적 UUID5로 변환
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, conversation_id))


class VectorRepository:
    def __init__(self, client: AsyncQdrantClient):
        self.client = client

    async def ensure_collection(self) -> None:
        # 컬렉션이 없을 때만 생성 — 앱 재시작 시 매번 호출해도 안전
        if not await self.client.collection_exists(COLLECTION):
            await self.client.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )

    async def upsert(self, conversation_id: str, vector: list[float], payload: dict) -> str:
        # upsert: 같은 ID가 이미 있으면 덮어씀 → 임베딩 재생성 시 중복 없이 갱신 가능
        pid = _point_id(conversation_id)
        await self.client.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(id=pid, vector=vector, payload=payload)],
        )
        return pid

    async def search(self, vector: list[float], owner_id: str, limit: int) -> list:
        # owner_id 필터로 다른 사용자의 대화가 검색 결과에 섞이지 않도록 격리
        result = await self.client.query_points(
            collection_name=COLLECTION,
            query=vector,
            query_filter=Filter(
                must=[FieldCondition(key="owner_id", match=MatchValue(value=owner_id))]
            ),
            limit=limit,
            with_payload=True,
        )
        return result.points

    async def delete(self, conversation_id: str) -> None:
        await self.client.delete(
            collection_name=COLLECTION,
            points_selector=PointIdsList(points=[_point_id(conversation_id)]),
        )
