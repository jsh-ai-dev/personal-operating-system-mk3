from dataclasses import asdict
import re

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.adapter.mongodb.diet_repository import DietRepository
from app.application.chat_service import OPENAI_PRICING
from app.application.diet_service import DEFAULT_DIET_MODEL, DietService
from app.core.auth import AuthUser, get_current_user
from app.core.config import settings
from app.core.dependencies import get_db

router = APIRouter(prefix="/diet", tags=["diet"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _get_svc(db: AsyncIOMotorDatabase = Depends(get_db)) -> DietService:
    return DietService(DietRepository(db), AsyncOpenAI(api_key=settings.openai_api_key))


class DietProfileRequest(BaseModel):
    current_weight_kg: float | None = Field(default=None, ge=0)
    target_weight_kg: float | None = Field(default=None, ge=0)
    daily_calories: int | None = Field(default=None, ge=0)
    protein_g: int | None = Field(default=None, ge=0)
    carbs_g: int | None = Field(default=None, ge=0)
    fat_g: int | None = Field(default=None, ge=0)


class AnalyzeDietRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    model: str = DEFAULT_DIET_MODEL


class CopyMealRequest(BaseModel):
    source_date_key: str
    source_meal_key: str
    target_meal_key: str


def _validate_date_key(date_key: str) -> None:
    if not _DATE_RE.match(date_key):
        raise HTTPException(status_code=400, detail="date_key must be YYYY-MM-DD")


@router.get("/profile")
async def get_profile(
    svc: DietService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return asdict(await svc.get_profile(user.id))


@router.put("/profile")
async def upsert_profile(
    body: DietProfileRequest,
    svc: DietService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return asdict(await svc.upsert_profile(user.id, body.model_dump()))


@router.get("/days/recent-meals")
async def list_recent_meals(
    days: int = 14,
    limit: int = 20,
    svc: DietService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    return {
        "candidates": await svc.list_recent_meal_candidates(
            user.id,
            days=days,
            limit=limit,
        )
    }


@router.get("/days/{date_key}")
async def get_day(
    date_key: str,
    svc: DietService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    _validate_date_key(date_key)
    return asdict(await svc.get_day(user.id, date_key))


@router.delete("/days/{date_key}", status_code=204)
async def delete_day(
    date_key: str,
    svc: DietService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    _validate_date_key(date_key)
    await svc.delete_day(user.id, date_key)


@router.post("/days/{date_key}/copy-meal")
async def copy_meal(
    date_key: str,
    body: CopyMealRequest,
    svc: DietService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    _validate_date_key(date_key)
    _validate_date_key(body.source_date_key)
    try:
        return asdict(
            await svc.copy_meal(
                owner_id=user.id,
                source_date_key=body.source_date_key,
                source_meal_key=body.source_meal_key,
                target_date_key=date_key,
                target_meal_key=body.target_meal_key,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/days/{date_key}/analyze")
async def analyze_day(
    date_key: str,
    body: AnalyzeDietRequest,
    svc: DietService = Depends(_get_svc),
    user: AuthUser = Depends(get_current_user),
):
    _validate_date_key(date_key)
    if body.model not in OPENAI_PRICING:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 모델: {body.model}")
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY가 설정되지 않았습니다")
    try:
        return await svc.analyze_day(user.id, date_key, body.message.strip(), body.model)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"식단 분석에 실패했습니다. ({e})")
