# [라우터] v1 버전 API의 모든 엔드포인트를 하나로 묶는 루트 라우터
# 새 도메인 추가 시 여기에 include_router만 추가하면 됨

from fastapi import APIRouter

from app.api.v1 import health, ai_services

# v1 버전의 모든 엔드포인트를 하나로 묶는 루트 라우터
# 새 도메인 추가 시 여기에 include_router만 추가하면 됨
router = APIRouter()
router.include_router(health.router)
router.include_router(ai_services.router)
