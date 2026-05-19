from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase


ACTIVE_STATUSES = ["queued", "running"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class NewsScrapeJobRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db["news_scrape_jobs"]

    def _to_api(self, doc: dict | None) -> dict | None:
        if not doc:
            return None
        out = dict(doc)
        out["id"] = str(out.pop("_id"))
        return out

    async def create(self, owner_id: str, date: str) -> dict:
        now = _now_iso()
        doc = {
            "owner_id": owner_id,
            "date": date,
            "status": "queued",
            "total": 0,
            "processed": 0,
            "inserted": 0,
            "skipped_existing": 0,
            "failed": 0,
            "message": "Scrape job queued.",
            "last_error": "",
            "current_url": "",
            "errors": [],
            "created_at": now,
            "updated_at": now,
            "started_at": "",
            "finished_at": "",
            "cooldown_until": "",
        }
        result = await self.col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return self._to_api(doc)

    async def find_active(self, owner_id: str, date: str) -> dict | None:
        doc = await self.col.find_one(
            {"owner_id": owner_id, "date": date, "status": {"$in": ACTIVE_STATUSES}},
            sort=[("created_at", -1)],
        )
        return self._to_api(doc)

    async def find_latest(self, owner_id: str, date: str | None = None) -> dict | None:
        query: dict[str, Any] = {"owner_id": owner_id}
        if date:
            query["date"] = date
        doc = await self.col.find_one(query, sort=[("created_at", -1)])
        return self._to_api(doc)

    async def find_by_id(self, job_id: str, owner_id: str) -> dict | None:
        try:
            oid = ObjectId(job_id)
        except InvalidId:
            return None
        doc = await self.col.find_one({"_id": oid, "owner_id": owner_id})
        return self._to_api(doc)

    async def update(self, job_id: str, **fields: Any) -> dict | None:
        try:
            oid = ObjectId(job_id)
        except InvalidId:
            return None
        fields["updated_at"] = _now_iso()
        await self.col.update_one({"_id": oid}, {"$set": fields})
        doc = await self.col.find_one({"_id": oid})
        return self._to_api(doc)

    async def append_error(self, job_id: str, message: str) -> None:
        try:
            oid = ObjectId(job_id)
        except InvalidId:
            return
        await self.col.update_one(
            {"_id": oid},
            {
                "$set": {"updated_at": _now_iso(), "last_error": message},
                "$push": {"errors": {"$each": [message], "$slice": -20}},
            },
        )
