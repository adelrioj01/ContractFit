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
