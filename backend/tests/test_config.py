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


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_hosted_postgres_url_uses_installed_driver(scheme: str) -> None:
    suffix = "user:p%25word@db.internal/demo?sslmode=require"
    settings = Settings(database_url=f"{scheme}://{suffix}", _env_file=None)
    assert settings.database_url == f"postgresql+psycopg://{suffix}"


def test_sqlite_url_is_preserved() -> None:
    assert Settings(database_url="sqlite://", _env_file=None).database_url == "sqlite://"


def test_alembic_accepts_url_encoded_password_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    import sys
    from pathlib import Path

    monkeypatch.setenv("DATABASE_URL", "postgres://demo:p%25word@localhost/demo")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "CREATE EXTENSION IF NOT EXISTS vector" in result.stdout
    assert "20261106_0018" in result.stdout
