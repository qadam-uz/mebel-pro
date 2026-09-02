import pytest
from app.core.config import Settings
from pydantic import ValidationError

MINIO_ENV_KEYS = (
    "MINIO_ENDPOINT_URL",
    "MINIO_REGION",
    "MINIO_ACCESS_KEY_ID",
    "MINIO_SECRET_ACCESS_KEY",
    "MINIO_BUCKET",
    "MINIO_USE_SSL",
)


def clear_env(monkeypatch: pytest.MonkeyPatch, *keys: str) -> None:
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_trusted_proxy_cidrs_parse_from_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", '["172.29.0.0/24", "10.0.0.0/8"]')

    settings = Settings(ENV="dev", _env_file=None)

    assert settings.TRUSTED_PROXY_CIDRS == ["172.29.0.0/24", "10.0.0.0/8"]


def test_dev_minio_defaults_match_local_compose_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_env(monkeypatch, *MINIO_ENV_KEYS)

    settings = Settings(ENV="dev", _env_file=None)

    assert settings.MINIO_ENDPOINT_URL == "http://localhost:9000"
    assert settings.MINIO_ACCESS_KEY_ID == "mebel"
    assert settings.MINIO_SECRET_ACCESS_KEY == "mebel-secret"
    assert len(settings.MINIO_SECRET_ACCESS_KEY) >= 8
    assert settings.MINIO_BUCKET == "mebel"


def _prod_settings(**overrides: object) -> Settings:
    """A fully configured production Settings, minus whatever the test breaks."""
    values: dict[str, object] = {
        "ENV": "prod",
        "TELEGRAM_BOT_TOKEN": "bot-token",
        "TELEGRAM_BOT_USERNAME": "mebelpro_bot",
        "TELEGRAM_WEBHOOK_SECRET": "webhook-secret",
        "TELEGRAM_LOGIN_CODE_PEPPER": "prod-pepper",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]  # kwargs are settings fields


def test_dev_mode_defaults_off_so_a_missing_setting_cannot_open_sign_in() -> None:
    settings = Settings(ENV="dev", _env_file=None)

    assert settings.TELEGRAM_LOGIN_DEV_MODE is False
    assert settings.ALLOW_PROD_TELEGRAM_LOGIN_DEV_MODE is False
    assert settings.TELEGRAM_LOGIN_RATE_LIMITS_ENABLED is True


def test_dev_mode_is_rejected_in_prod() -> None:
    with pytest.raises(ValidationError, match="TELEGRAM_LOGIN_DEV_MODE"):
        _prod_settings(TELEGRAM_LOGIN_DEV_MODE=True)


def test_prod_dev_mode_requires_explicit_testing_override() -> None:
    """The pre-production escape hatch: dev mode before the bot is registered."""
    settings = _prod_settings(
        TELEGRAM_LOGIN_DEV_MODE=True,
        ALLOW_PROD_TELEGRAM_LOGIN_DEV_MODE=True,
        TELEGRAM_BOT_TOKEN="",
        TELEGRAM_BOT_USERNAME="",
        TELEGRAM_WEBHOOK_SECRET="",
        TELEGRAM_LOGIN_CODE_PEPPER="{{change-me}}",
    )

    assert settings.TELEGRAM_LOGIN_DEV_MODE is True


@pytest.mark.parametrize(
    "field",
    [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_BOT_USERNAME",
        "TELEGRAM_WEBHOOK_SECRET",
        "TELEGRAM_LOGIN_CODE_PEPPER",
    ],
)
def test_prod_requires_every_bot_secret(field: str) -> None:
    """An unset bot secret is a boot failure, not a silently disabled bot."""
    with pytest.raises(ValidationError, match=field):
        _prod_settings(**{field: "{{change-me}}"})

    assert _prod_settings().TELEGRAM_API_BASE_URL == "https://api.telegram.org"
