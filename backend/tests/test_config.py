"""Prod-safety guardrails on Settings (`app/core/config.py`).

The backend must fail-closed at startup rather than run with dev defaults that
would be unsafe in production — an empty Telegram bot token (which silently
skips client sign-in signature verification) or the public docs password.
"""

import pytest
from app.core.config import Settings
from pydantic import ValidationError


def _prod_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ENV": "prod",
        "TELEGRAM_BOT_TOKEN": "real-bot-token",
        "DOCS_AUTH_PASSWORD": "a-strong-secret",
    }
    base.update(overrides)
    return base


def test_prod_refuses_empty_telegram_token() -> None:
    with pytest.raises(ValidationError, match="TELEGRAM_BOT_TOKEN"):
        Settings(**_prod_kwargs(TELEGRAM_BOT_TOKEN=""))


def test_prod_refuses_default_docs_password() -> None:
    with pytest.raises(ValidationError, match="DOCS_AUTH_PASSWORD"):
        Settings(**_prod_kwargs(DOCS_AUTH_PASSWORD="docs"))


def test_prod_boots_with_real_secrets() -> None:
    settings = Settings(**_prod_kwargs())
    assert settings.ENV == "prod"


def test_dev_allows_empty_telegram_token() -> None:
    # Dev convenience: no bot needed, signature check is skipped downstream.
    settings = Settings(ENV="dev", TELEGRAM_BOT_TOKEN="", DOCS_AUTH_PASSWORD="docs")
    assert settings.TELEGRAM_BOT_TOKEN == ""
