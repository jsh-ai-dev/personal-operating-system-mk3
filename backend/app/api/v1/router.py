from fastapi import APIRouter

from app.api.v1 import health

# v1 버전의 모든 엔드포인트를 하나로 묶는 루트 라우터
# 새 도메인(예: user, task) 추가 시 여기에 include_router만 추가하면 됨
router = APIRouter()
router.include_router(health.router)
