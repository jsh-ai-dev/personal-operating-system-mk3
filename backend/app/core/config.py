# [설정] 환경변수와 .env 파일을 읽어 앱 전체 설정값을 관리하는 파일
# pydantic-settings의 BaseSettings를 사용해 타입 안전하게 설정을 주입함

from pydantic_settings import BaseSettings, SettingsConfigDict


# BaseSettings: .env 파일과 환경변수를 읽어 필드에 자동으로 바인딩해줌
# extra="ignore": .env에 정의되지 않은 필드가 있어도 오류 없이 무시
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # MongoDB 연결 설정 (기본값은 로컬 Docker Compose 기준)
    mongodb_url: str = "mongodb://pos:pos@localhost:27017"
    mongodb_db: str = "pos_mk3"

    # Qdrant (벡터 DB) 연결 설정
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None  # 로컬 환경에서는 API 키 불필요

    # AI API 키
    openai_api_key: str | None = None

    # CORS 허용 출처 목록 (프론트엔드 주소를 추가해야 브라우저에서 API 호출 가능)
    cors_origins: list[str] = ["http://localhost:3003"]

    # JetBrains AI Assistant 세션 히스토리 경로 (B 방식 임포트용)
    # IDE 버전이 바뀌면 경로도 바뀌니 .env에서 재정의 가능
    jetbrains_aia_path: str = r"C:\Users\USER\AppData\Roaming\JetBrains\IntelliJIdea2026.1\aia-task-history"


# 모듈 로드 시 한 번만 생성 — 앱 전체에서 이 인스턴스를 임포트해 공유
settings = Settings()
