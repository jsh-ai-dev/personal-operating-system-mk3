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
    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None

    # CORS 허용 출처 목록 (프론트엔드 주소를 추가해야 브라우저에서 API 호출 가능)
    cors_origins: list[str] = ["http://localhost:3003"]
    auth_service_url: str = "http://127.0.0.1:3002"

    # JetBrains AI Assistant 세션 히스토리 경로 (B 방식 임포트용)
    # AppData 대신 data/codex 로 통일 — 다른 서비스와 동일한 data/ 루트 기준
    jetbrains_aia_path: str = r"data\codex"

    # Google Takeout 내활동.json 경로 (Gemini 대화 임포트용)
    gemini_takeout_path: str = r"data\gemini\내활동.json"

    # Claude.ai 데이터 내보내기 경로 (Claude 대화 임포트용)
    claude_export_path: str = r"data\claude\conversations.json"

    # Claude Code 로컬 트랜스크립트 디렉토리 (Claude Code 대화 임포트용)
    claude_code_path: str = r"data\claude-code"

    # ChatGPT 데이터 내보내기 경로 (ChatGPT 대화 임포트용)
    chatgpt_export_path: str = r"data\chatgpt\conversations.json"

    # AWS S3 설정 — 설정 시 로컬 data/ 경로 대신 S3에서 파일을 읽음
    # 로컬 개발: IAM 사용자 액세스 키 사용 / AWS 배포 시: IAM Role로 대체(키 불필요)
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "ap-northeast-2"
    s3_bucket: str | None = None
    # s3_prefix: 버킷 내 공통 상위 폴더 (예: "pos-mk3-import-data") — 비워두면 버킷 루트 사용
    s3_prefix: str = ""


# 모듈 로드 시 한 번만 생성 — 앱 전체에서 이 인스턴스를 임포트해 공유
settings = Settings()
