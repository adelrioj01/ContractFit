import pytest
from pydantic import ValidationError

from contractfit.config import Settings


def test_production_rejects_development_auth_secret() -> None:
    with pytest.raises(ValidationError, match="private AUTH_SECRET_KEY"):
        Settings(app_env="production", _env_file=None)


def test_production_accepts_private_auth_secret() -> None:
    settings = Settings(
        app_env="production",
        auth_secret_key="a-private-production-secret-with-32-bytes",
        _env_file=None,
    )

    assert settings.app_env == "production"


def test_ollama_embeddings_require_schema_dimension() -> None:
    with pytest.raises(ValidationError, match="768-dimensional"):
        Settings(embedding_provider="ollama", embedding_dimensions=384)


def test_scheduled_sam_sync_requires_api_key() -> None:
    with pytest.raises(ValidationError, match="SAM_API_KEY"):
        Settings(sam_sync_enabled=True, sam_api_key="", _env_file=None)


def test_scheduled_sam_sync_accepts_api_key() -> None:
    settings = Settings(
        sam_sync_enabled=True,
        sam_api_key="test-key",
        sam_page_size=250,
        _env_file=None,
    )

    assert settings.sam_sync_enabled is True
    assert settings.sam_page_size == 250
