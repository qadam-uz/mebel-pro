import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_otp_dev_codes_parse_from_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTP_DEV_CODES", '["000000", "111111"]')

    settings = Settings(ENV="dev")

    assert settings.OTP_DEV_CODES == ["000000", "111111"]


def test_otp_dev_codes_are_rejected_in_prod() -> None:
    with pytest.raises(ValidationError, match="OTP_DEV_CODES"):
        Settings(ENV="prod", OTP_DEV_CODES=["000000"])
