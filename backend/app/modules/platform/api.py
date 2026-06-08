"""Public platform API used by routes and other modules."""

from typing import TYPE_CHECKING, Any

from app.modules.platform.errors import record_application_error

if TYPE_CHECKING:
    from app.modules.platform.service import (
        CreatedPlatformUser,
        PlatformJobRecord,
        ProvisionedWorkshop,
        block_platform_user,
        block_workshop,
        create_platform_user,
        generate_temp_password,
        get_error_record_detail,
        get_workshop_detail,
        list_error_records,
        list_platform_action_logs,
        list_platform_jobs,
        list_platform_status_change_logs,
        list_platform_users,
        list_workshops,
        provision_workshop,
        require_platform_operator,
        reset_platform_user_password,
        resolve_error_record,
        run_platform_job,
        unblock_platform_user,
        unblock_workshop,
        update_platform_user,
    )

_SERVICE_EXPORTS = {
    "CreatedPlatformUser",
    "PlatformJobRecord",
    "ProvisionedWorkshop",
    "block_platform_user",
    "block_workshop",
    "create_platform_user",
    "generate_temp_password",
    "get_error_record_detail",
    "get_workshop_detail",
    "list_error_records",
    "list_platform_action_logs",
    "list_platform_jobs",
    "list_platform_status_change_logs",
    "list_platform_users",
    "list_workshops",
    "provision_workshop",
    "require_platform_operator",
    "reset_platform_user_password",
    "resolve_error_record",
    "run_platform_job",
    "unblock_platform_user",
    "unblock_workshop",
    "update_platform_user",
}


def __getattr__(name: str) -> Any:
    if name in _SERVICE_EXPORTS:
        from app.modules.platform import service

        return getattr(service, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CreatedPlatformUser",
    "PlatformJobRecord",
    "ProvisionedWorkshop",
    "block_platform_user",
    "block_workshop",
    "create_platform_user",
    "generate_temp_password",
    "get_error_record_detail",
    "get_workshop_detail",
    "list_error_records",
    "list_platform_action_logs",
    "list_platform_jobs",
    "list_platform_status_change_logs",
    "list_platform_users",
    "list_workshops",
    "provision_workshop",
    "record_application_error",
    "require_platform_operator",
    "reset_platform_user_password",
    "resolve_error_record",
    "run_platform_job",
    "unblock_platform_user",
    "unblock_workshop",
    "update_platform_user",
]
