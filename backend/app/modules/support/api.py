"""Public support API used by other modules."""

from typing import TYPE_CHECKING, Any

from app.modules.support.audit import (
    list_action_logs,
    list_status_change_logs,
    record_action,
    record_status_change,
    scrub_sensitive,
    scrub_text,
)
from app.modules.support.image_variants import (
    ImageVariant,
    resolve_variant,
)
from app.modules.support.notifications import (
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    unread_count,
)
from app.modules.support.telegram_delivery import (
    PendingTelegramMessage,
    deliver_client_telegram_message,
    queue_client_order_message,
    render_order_message,
)

if TYPE_CHECKING:
    from app.modules.support.files import (
        FILE_CACHE_CONTROL,
        IMAGE_CONTENT_TYPES,
        RECEIPT_CONTENT_TYPES,
        FileStorage,
        InMemoryFileStorage,
        S3FileStorage,
        StoredObject,
        attach_file,
        build_image_variants,
        create_uploaded_file,
        file_storage,
        get_file_for_read,
        get_stored_file,
        replace_attached_file,
        serve_stored_file,
    )

_FILE_EXPORTS = {
    "FILE_CACHE_CONTROL",
    "IMAGE_CONTENT_TYPES",
    "RECEIPT_CONTENT_TYPES",
    "FileStorage",
    "InMemoryFileStorage",
    "S3FileStorage",
    "StoredObject",
    "attach_file",
    "build_image_variants",
    "create_uploaded_file",
    "file_storage",
    "get_file_for_read",
    "get_stored_file",
    "replace_attached_file",
    "serve_stored_file",
}


def __getattr__(name: str) -> Any:
    if name in _FILE_EXPORTS:
        from app.modules.support import files

        return getattr(files, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "FILE_CACHE_CONTROL",
    "IMAGE_CONTENT_TYPES",
    "RECEIPT_CONTENT_TYPES",
    "FileStorage",
    "ImageVariant",
    "InMemoryFileStorage",
    "PendingTelegramMessage",
    "S3FileStorage",
    "StoredObject",
    "attach_file",
    "build_image_variants",
    "create_uploaded_file",
    "deliver_client_telegram_message",
    "file_storage",
    "get_file_for_read",
    "get_stored_file",
    "list_action_logs",
    "list_notifications",
    "list_status_change_logs",
    "mark_all_notifications_read",
    "mark_notification_read",
    "queue_client_order_message",
    "record_action",
    "record_status_change",
    "render_order_message",
    "replace_attached_file",
    "resolve_variant",
    "scrub_sensitive",
    "scrub_text",
    "serve_stored_file",
    "unread_count",
]
