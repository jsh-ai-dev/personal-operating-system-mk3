# [스크래퍼 메타 저장소] 마지막 갱신 시각을 MongoDB에 저장/조회하는 어댑터
# 사용자별로 1개의 문서만 유지하며, 갱신할 때마다 upsert로 덮어씀

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase


class ScraperMetaRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db["scraper_meta"]

    async def get_last_synced_at(self, owner_id: str) -> str | None:
        doc = await self.col.find_one({"owner_id": owner_id})
        return doc.get("last_synced_at") if doc else None

    async def set_last_synced_at(self, owner_id: str) -> str:
        now = datetime.now(timezone.utc).isoformat()
        await self.col.update_one(
            {"owner_id": owner_id},
            {"$set": {"last_synced_at": now}},
            upsert=True,
        )
        return now
