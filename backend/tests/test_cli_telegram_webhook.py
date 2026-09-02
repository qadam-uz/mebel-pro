"""The `telegram-webhook` maintenance CLI — a thin wrapper over one Bot API call.

What earns coverage here is the wrapper's own logic: the webhook URL derivation,
the secret refusing to register unset, and the flag pass-through. The Bot API
itself is faked at the `telegram.call` seam.
"""

import json
from typing import Any

import pytest
from app import cli
from app.core import telegram
from app.core.config import settings


@pytest.fixture()
def recorded_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_call(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append((method, payload))
        return {"url": "https://example.test/hook"}

    monkeypatch.setattr(telegram, "call", fake_call)
    return calls


def test_set_derives_url_from_client_app_base_url(
    monkeypatch: pytest.MonkeyPatch,
    recorded_calls: list[tuple[str, dict[str, Any]]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "hook-secret")
    monkeypatch.setattr(settings, "CLIENT_APP_BASE_URL", "https://app.mebel-pro.uz/")

    cli.main(["telegram-webhook", "set"])

    assert recorded_calls == [
        (
            "setWebhook",
            {
                "url": "https://app.mebel-pro.uz/api/v1/telegram/webhook",
                "secret_token": "hook-secret",
                "allowed_updates": ["message", "callback_query"],
            },
        )
    ]
    assert json.loads(capsys.readouterr().out) == {
        "status": "set",
        "url": "https://app.mebel-pro.uz/api/v1/telegram/webhook",
    }


def test_set_honors_base_url_override_and_drop_flag(
    monkeypatch: pytest.MonkeyPatch,
    recorded_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "hook-secret")
    monkeypatch.setattr(settings, "CLIENT_APP_BASE_URL", "https://app.mebel-pro.uz")

    cli.main(
        [
            "telegram-webhook",
            "set",
            "--base-url",
            "https://staging.mebel-pro.uz",
            "--drop-pending-updates",
        ]
    )

    method, payload = recorded_calls[0]
    assert method == "setWebhook"
    assert payload["url"] == "https://staging.mebel-pro.uz/api/v1/telegram/webhook"
    assert payload["drop_pending_updates"] is True


@pytest.mark.parametrize("secret", ["", "{{change-me}}"])
def test_set_refuses_without_a_real_webhook_secret(
    monkeypatch: pytest.MonkeyPatch,
    recorded_calls: list[tuple[str, dict[str, Any]]],
    secret: str,
) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", secret)

    with pytest.raises(SystemExit):
        cli.main(["telegram-webhook", "set"])

    assert recorded_calls == []


def test_info_prints_the_bot_api_answer(
    recorded_calls: list[tuple[str, dict[str, Any]]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli.main(["telegram-webhook", "info"])

    assert recorded_calls == [("getWebhookInfo", {})]
    assert json.loads(capsys.readouterr().out) == {"url": "https://example.test/hook"}


def test_delete_passes_the_drop_flag(
    recorded_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    cli.main(["telegram-webhook", "delete", "--drop-pending-updates"])

    assert recorded_calls == [("deleteWebhook", {"drop_pending_updates": True})]


def test_api_refusal_exits_with_a_message_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "hook-secret")

    async def refusing_call(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise telegram.TelegramApiError("HTTP 400: bad webhook: HTTPS url must be provided")

    monkeypatch.setattr(telegram, "call", refusing_call)

    with pytest.raises(SystemExit, match="HTTPS url must be provided"):
        cli.main(["telegram-webhook", "set"])
