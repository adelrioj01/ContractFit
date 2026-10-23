from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://contractfit:contractfit@localhost:5432/contractfit"
    redis_url: str = "redis://localhost:6379/0"
    ai_provider: Literal["offline", "ollama"] = "offline"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    storage_backend: Literal["memory", "postgres"] = "memory"
    seed_demo_data: bool = True
    upload_directory: str = "data/uploads"
    upload_max_bytes: int = 20 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
