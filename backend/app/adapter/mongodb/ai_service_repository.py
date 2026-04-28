# [MongoDB 어댑터] AI 서비스 데이터를 MongoDB에 저장/조회/수정/삭제하는 클래스
# 도메인 모델(AIService)과 MongoDB 문서(dict) 사이의 변환을 담당함

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.ai_service import AIService


class AIServiceRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db["ai_services"]

    def _to_domain(self, doc: dict) -> AIService:
        # MongoDB의 _id(ObjectId)를 문자열 id로 변환
        return AIService(
            id=str(doc["_id"]),
            name=doc["name"],
            plan_name=doc.get("plan_name"),
            monthly_cost=doc.get("monthly_cost"),
            currency=doc.get("currency", "USD"),
            billing_day=doc.get("billing_day"),
            next_billing_date=doc.get("next_billing_date"),
            usage_limit=doc.get("usage_limit"),
            usage_current=doc.get("usage_current"),
            usage_unit=doc.get("usage_unit"),
            billing_url=doc.get("billing_url"),
            notes=doc.get("notes"),
        )

    async def find_all(self, owner_id: str) -> list[AIService]:
        docs = await self.col.find({"owner_id": owner_id}).sort("name", 1).to_list(None)
        return [self._to_domain(doc) for doc in docs]

    async def find_by_name(self, name: str, owner_id: str) -> AIService | None:
        # 이름으로 서비스 조회 (대소문자 구분 없음)
        doc = await self.col.find_one(
            {
                "owner_id": owner_id,
                "name": {"$regex": f"^{name}$", "$options": "i"},
            }
        )
        return self._to_domain(doc) if doc else None

    async def find_by_id(self, id: str, owner_id: str) -> AIService | None:
        try:
            doc = await self.col.find_one({"_id": ObjectId(id), "owner_id": owner_id})
        except InvalidId:
            return None
        return self._to_domain(doc) if doc else None

    async def insert(self, data: dict, owner_id: str) -> AIService:
        payload = {**data, "owner_id": owner_id}
        result = await self.col.insert_one(payload)
        return await self.find_by_id(str(result.inserted_id), owner_id)

    async def update(self, id: str, data: dict, owner_id: str) -> AIService | None:
        try:
            await self.col.update_one(
                {"_id": ObjectId(id), "owner_id": owner_id},
                {"$set": data},
            )
        except InvalidId:
            return None
        return await self.find_by_id(id, owner_id)

    async def delete(self, id: str, owner_id: str) -> bool:
        try:
            result = await self.col.delete_one({"_id": ObjectId(id), "owner_id": owner_id})
        except InvalidId:
            return False
        return result.deleted_count > 0
