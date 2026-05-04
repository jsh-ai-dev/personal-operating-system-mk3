# [저장소] 신문 기사(Article)의 MongoDB CRUD 담당
# Clean Architecture 어댑터 레이어 — 도메인 모델과 MongoDB 문서(dict) 간 변환 책임

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.article import Article, ArticleAnalysis


class ArticleRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db["news_articles"]

    def _to_domain(self, doc: dict) -> Article:
        analysis = None
        if doc.get("analysis"):
            a = doc["analysis"]
            analysis = ArticleAnalysis(
                highlighted_html=a.get("highlighted_html", ""),
                keywords=a.get("keywords", []),
                motivation_summary=a.get("motivation_summary", ""),
                questions=a.get("questions", []),
                analyzed_at=a.get("analyzed_at", ""),
            )
        return Article(
            id=str(doc["_id"]),
            date=doc["date"],
            page_num=doc["page_num"],
            title=doc["title"],
            url=doc["url"],
            content=doc["content"],
            companies=doc.get("companies", []),
            tags=doc.get("tags", []),
            scraped_at=doc.get("scraped_at", ""),
            analysis=analysis,
        )

    async def find_by_date(self, date: str, owner_id: str) -> list[Article]:
        docs = await self.col.find(
            {"date": date, "owner_id": owner_id}
        ).sort("page_num", 1).to_list(None)
        return [self._to_domain(doc) for doc in docs]

    async def find_by_id(self, id: str, owner_id: str) -> Article | None:
        try:
            doc = await self.col.find_one({"_id": ObjectId(id), "owner_id": owner_id})
        except InvalidId:
            return None
        return self._to_domain(doc) if doc else None

    async def find_by_url(self, url: str, owner_id: str) -> Article | None:
        doc = await self.col.find_one({"url": url, "owner_id": owner_id})
        return self._to_domain(doc) if doc else None

    async def insert_many(self, articles: list[dict], owner_id: str) -> list[Article]:
        docs = [{**a, "owner_id": owner_id} for a in articles]
        result = await self.col.insert_many(docs)
        inserted = await self.col.find(
            {"_id": {"$in": result.inserted_ids}}
        ).to_list(None)
        return [self._to_domain(doc) for doc in inserted]

    async def update_analysis(self, id: str, owner_id: str, analysis: dict) -> Article | None:
        try:
            await self.col.update_one(
                {"_id": ObjectId(id), "owner_id": owner_id},
                {"$set": {"analysis": analysis}},
            )
        except InvalidId:
            return None
        return await self.find_by_id(id, owner_id)

    async def update_meta(self, id: str, owner_id: str, companies: list, tags: list) -> None:
        """스크랩 시 자동 추출한 기업명·태그를 저장한다."""
        try:
            await self.col.update_one(
                {"_id": ObjectId(id), "owner_id": owner_id},
                {"$set": {"companies": companies, "tags": tags}},
            )
        except InvalidId:
            pass
