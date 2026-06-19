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


def test_otp_dev_codes_parse_from_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTP_DEV_CODES", '["000000", "111111"]')

    settings = Settings(ENV="dev", _env_file=None)

    assert settings.OTP_DEV_CODES == ["000000", "111111"]


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


def test_otp_dev_codes_are_rejected_in_prod() -> None:
    with pytest.raises(ValidationError, match="OTP_DEV_CODES"):
        Settings(ENV="prod", OTP_DEV_CODES=["000000"], _env_file=None)


def test_prod_otp_dev_codes_require_explicit_testing_override() -> None:
    settings = Settings(
        ENV="prod",
        OTP_DEV_CODES=["000000"],
        ALLOW_PROD_OTP_DEV_CODES=True,
        OTP_CODE_PEPPER="{{change-me}}",
        TELEGRAM_GATEWAY_ACCESS_TOKEN="",
        _env_file=None,
    )

    assert settings.OTP_DEV_CODES == ["000000"]
    assert settings.ALLOW_PROD_OTP_DEV_CODES is True


def test_prod_requires_telegram_gateway_token_and_otp_pepper() -> None:
    with pytest.raises(ValidationError, match="TELEGRAM_GATEWAY_ACCESS_TOKEN"):
        Settings(
            ENV="prod",
            OTP_DEV_CODES=[],
            OTP_CODE_PEPPER="prod-pepper",
            TELEGRAM_GATEWAY_ACCESS_TOKEN="",
            _env_file=None,
        )
    with pytest.raises(ValidationError, match="OTP_CODE_PEPPER"):
        Settings(
            ENV="prod",
            OTP_DEV_CODES=[],
            OTP_CODE_PEPPER="{{change-me}}",
            TELEGRAM_GATEWAY_ACCESS_TOKEN="token",
            _env_file=None,
        )

    settings = Settings(
        ENV="prod",
        OTP_DEV_CODES=[],
        OTP_CODE_PEPPER="prod-pepper",
        TELEGRAM_GATEWAY_ACCESS_TOKEN="token",
        _env_file=None,
    )

    assert settings.TELEGRAM_GATEWAY_API_BASE_URL == "https://gatewayapi.telegram.org"
