from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://contractfit:contractfit@localhost:5432/contractfit"
    redis_url: str = "redis://localhost:6379/0"
    ai_provider: Literal["offline", "ollama"] = "offline"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    embedding_provider: Literal["disabled", "ollama"] = "disabled"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = Field(default=768, ge=1, le=4096)
    embedding_match_limit: int = Field(default=100, ge=1, le=1000)
    storage_backend: Literal["memory", "postgres"] = "memory"
    seed_demo_data: bool = True
    upload_directory: str = "data/uploads"
    upload_max_bytes: int = 20 * 1024 * 1024
    processing_mode: Literal["inline", "redis"] = "inline"
    processing_queue_name: str = "contractfit:document-jobs"
    ocr_backend: Literal["disabled", "tesseract"] = "disabled"
    tesseract_command: str = "tesseract"
    auth_secret_key: str = Field(
        default="development-only-change-me-32-bytes", min_length=32
    )
    auth_access_token_minutes: int = Field(default=60, ge=1, le=1440)
    sam_api_key: str | None = None
    sam_sync_enabled: bool = False
    sam_sync_interval_minutes: int = Field(default=360, ge=5, le=10080)
    sam_lookback_days: int = Field(default=7, ge=1, le=365)
    sam_page_size: int = Field(default=100, ge=1, le=1000)
    sam_request_timeout_seconds: float = Field(default=30.0, gt=0, le=300)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def production_requires_private_auth_secret(self) -> "Settings":
        if (
            self.app_env == "production"
            and self.auth_secret_key == "development-only-change-me-32-bytes"
        ):
            raise ValueError("production requires a private AUTH_SECRET_KEY")
        if self.embedding_provider == "ollama" and self.embedding_dimensions != 768:
            raise ValueError("the current pgvector schema requires 768-dimensional embeddings")
        if self.sam_sync_enabled and not (self.sam_api_key and self.sam_api_key.strip()):
            raise ValueError("SAM_SYNC_ENABLED requires a non-empty SAM_API_KEY")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
