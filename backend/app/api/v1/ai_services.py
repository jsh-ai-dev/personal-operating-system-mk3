# [AI 서비스 API] GET/POST/PUT/DELETE /api/v1/ai-services — AI 구독 서비스 CRUD 엔드포인트
# 요청/응답 스키마(Pydantic)와 라우터 핸들러를 함께 정의함

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.adapter.mongodb.ai_service_repository import AIServiceRepository
from app.application.ai_service_service import AIServiceService
from app.core.dependencies import get_db

router = APIRouter(prefix="/ai-services", tags=["ai-services"])


# 요청/응답 공통 스키마
class AIServiceBody(BaseModel):
    name: str
    plan_name: str | None = None
    monthly_cost: float | None = Field(default=None, ge=0)
    currency: str = "USD"
    billing_day: int | None = Field(default=None, ge=1, le=31)
    usage_limit: float | None = None
    usage_current: float | None = None
    usage_unit: str | None = None
    billing_url: str | None = None
    notes: str | None = None


# 응답에만 id 추가
class AIServiceResponse(AIServiceBody):
    id: str


def _get_svc(db: AsyncIOMotorDatabase = Depends(get_db)) -> AIServiceService:
    # 요청마다 repository와 service를 생성해 주입
    return AIServiceService(AIServiceRepository(db))


@router.get("", response_model=list[AIServiceResponse])
async def list_ai_services(svc: AIServiceService = Depends(_get_svc)):
    return [asdict(s) for s in await svc.list()]


@router.get("/{id}", response_model=AIServiceResponse)
async def get_ai_service(id: str, svc: AIServiceService = Depends(_get_svc)):
    service = await svc.get(id)
    if not service:
        raise HTTPException(status_code=404, detail="AI service not found")
    return asdict(service)


@router.post("", response_model=AIServiceResponse, status_code=201)
async def create_ai_service(body: AIServiceBody, svc: AIServiceService = Depends(_get_svc)):
    service = await svc.create(body.model_dump())
    return asdict(service)


@router.put("/{id}", response_model=AIServiceResponse)
async def update_ai_service(id: str, body: AIServiceBody, svc: AIServiceService = Depends(_get_svc)):
    service = await svc.update(id, body.model_dump())
    if not service:
        raise HTTPException(status_code=404, detail="AI service not found")
    return asdict(service)


@router.delete("/{id}", status_code=204)
async def delete_ai_service(id: str, svc: AIServiceService = Depends(_get_svc)):
    deleted = await svc.delete(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="AI service not found")
    return Response(status_code=204)
