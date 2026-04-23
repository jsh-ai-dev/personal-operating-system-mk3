from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_url: str = "mongodb://pos:pos@localhost:27017"
    mongodb_db: str = "pos_mk3"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None

    cors_origins: list[str] = ["http://localhost:3003"]


settings = Settings()
