from app.core.principal import system_actor
from app.modules.platform.api import record_application_error
from app.modules.platform.contracts import ErrorOccurrence
from app.modules.support.api import (
    InMemoryFileStorage,
    record_action,
    record_status_change,
    scrub_sensitive,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def test_scrub_sensitive_masks_nested_denylists() -> None:
    scrubbed = scrub_sensitive(
        {
            "password": "secret",
            "new_password": "secret",
            "passwordHash": "hash",
            "nested": [{"authorization": "Bearer secret"}, {"safe": "value"}],
            "refreshToken": "token",
            "message": "password=secret token:plain",
            "token_hash": "hash",
        }
    )

    assert scrubbed == {
        "password": "***",
        "new_password": "***",
        "passwordHash": "***",
        "nested": [{"authorization": "***"}, {"safe": "value"}],
        "refreshToken": "***",
        "message": "password=*** token:***",
        "token_hash": "***",
    }


async def test_action_and_status_logs_store_masked_details(db_session: AsyncSession) -> None:
    actor = system_actor("trace-1")
    action = await record_action(
        db_session,
        actor=actor,
        action="foundation.test",
        entity_type="test",
        summary="Test action",
        details={"otp_code": "123456", "safe": "kept"},
    )

    status = await record_status_change(
        db_session,
        actor=actor,
        entity_type="test",
        entity_id=action.id,
        from_status="old",
        to_status="new",
        action_log_id=action.id,
    )

    assert action.details == {"otp_code": "***", "safe": "kept"}
    assert action.trace_id == "trace-1"
    assert status.action_log_id == action.id


async def test_error_monitor_records_masked_occurrences(db_session: AsyncSession) -> None:
    record = await record_application_error(
        db_session,
        code="test.error",
        module="tests",
        message="A password=plain error",
        trace_id="trace-2",
        stack="RuntimeError: token=plain",
        context={"access_token": "plain", "safe": "value"},
    )
    await record_application_error(
        db_session,
        code="test.error",
        module="tests",
        message="A second occurrence",
        trace_id="trace-3",
        context={"refresh_token": "plain"},
    )

    occurrence = await db_session.scalar(
        select(ErrorOccurrence).where(ErrorOccurrence.trace_id == "trace-2")
    )

    assert record.count_24h == 2
    assert record.count_7d == 2
    assert record.preview_message == "A second occurrence"
    assert occurrence is not None
    assert occurrence.message == "A password=*** error"
    assert occurrence.stack == "RuntimeError: token=***"
    assert occurrence.context == {"access_token": "***", "safe": "value"}


def test_in_memory_file_storage_round_trips_and_deletes_content() -> None:
    storage = InMemoryFileStorage()

    stored = storage.put("files/demo.txt", b"demo", "text/plain")

    assert stored.size_bytes == 4
    assert storage.open("files/demo.txt") == b"demo"
    storage.delete("files/demo.txt")
    assert "files/demo.txt" not in storage.objects
