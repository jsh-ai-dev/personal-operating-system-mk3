# [서비스 레이어] AI 서비스 CRUD 비즈니스 로직을 담당하는 클래스
# API 레이어와 Repository 사이에 위치하며, 유효성 검사나 추가 로직이 필요하면 여기에 추가함

from app.adapter.mongodb.ai_service_repository import AIServiceRepository
from app.domain.ai_service import AIService


class AIServiceService:
    def __init__(self, repo: AIServiceRepository):
        self.repo = repo

    async def list(self) -> list[AIService]:
        return await self.repo.find_all()

    async def get(self, id: str) -> AIService | None:
        return await self.repo.find_by_id(id)

    async def create(self, data: dict) -> AIService:
        return await self.repo.insert(data)

    async def update(self, id: str, data: dict) -> AIService | None:
        return await self.repo.update(id, data)

    async def delete(self, id: str) -> bool:
        return await self.repo.delete(id)
