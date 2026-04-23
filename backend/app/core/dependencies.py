# [의존성 주입] FastAPI의 Depends()와 함께 사용할 의존성 함수들을 정의
# 엔드포인트에서 DB 클라이언트를 직접 생성하지 않고 이 파일을 통해 주입받음

from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from qdrant_client import AsyncQdrantClient

from app.core.config import settings


# FastAPI의 Depends()와 함께 사용하는 의존성 주입 함수들
# 엔드포인트에서 직접 DB 클라이언트를 만들지 않고 여기서 주입받음
# → 테스트 시 이 함수만 교체하면 전체 DB를 목으로 대체할 수 있음

def get_db(request: Request) -> AsyncIOMotorDatabase:
    # lifespan에서 app.state.mongo에 저장해둔 클라이언트에서 DB를 선택해 반환
    return request.app.state.mongo[settings.mongodb_db]


def get_qdrant(request: Request) -> AsyncQdrantClient:
    return request.app.state.qdrant
