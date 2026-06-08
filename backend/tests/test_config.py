import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_otp_dev_codes_parse_from_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTP_DEV_CODES", '["000000", "111111"]')

    settings = Settings(ENV="dev")

    assert settings.OTP_DEV_CODES == ["000000", "111111"]


def test_dev_minio_defaults_match_local_compose_credentials() -> None:
    settings = Settings(ENV="dev")

    assert settings.MINIO_ENDPOINT_URL == "http://localhost:9000"
    assert settings.MINIO_ACCESS_KEY_ID == "mebel"
    assert settings.MINIO_SECRET_ACCESS_KEY == "mebel-secret"
    assert len(settings.MINIO_SECRET_ACCESS_KEY) >= 8
    assert settings.MINIO_BUCKET == "mebel"


def test_otp_dev_codes_are_rejected_in_prod() -> None:
    with pytest.raises(ValidationError, match="OTP_DEV_CODES"):
        Settings(ENV="prod", OTP_DEV_CODES=["000000"])


def test_prod_requires_telegram_gateway_token_and_otp_pepper() -> None:
    with pytest.raises(ValidationError, match="TELEGRAM_GATEWAY_ACCESS_TOKEN"):
        Settings(
            ENV="prod",
            OTP_DEV_CODES=[],
            OTP_CODE_PEPPER="prod-pepper",
            TELEGRAM_GATEWAY_ACCESS_TOKEN="",
        )
    with pytest.raises(ValidationError, match="OTP_CODE_PEPPER"):
        Settings(
            ENV="prod",
            OTP_DEV_CODES=[],
            OTP_CODE_PEPPER="{{change-me}}",
            TELEGRAM_GATEWAY_ACCESS_TOKEN="token",
        )

    settings = Settings(
        ENV="prod",
        OTP_DEV_CODES=[],
        OTP_CODE_PEPPER="prod-pepper",
        TELEGRAM_GATEWAY_ACCESS_TOKEN="token",
    )

    assert settings.TELEGRAM_GATEWAY_API_BASE_URL == "https://gatewayapi.telegram.org"
