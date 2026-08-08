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

if TYPE_CHECKING:
    from app.modules.support.files import (
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
        replace_attached_file,
    )

_FILE_EXPORTS = {
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
    "replace_attached_file",
}


def __getattr__(name: str) -> Any:
    if name in _FILE_EXPORTS:
        from app.modules.support import files

        return getattr(files, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "IMAGE_CONTENT_TYPES",
    "RECEIPT_CONTENT_TYPES",
    "FileStorage",
    "ImageVariant",
    "InMemoryFileStorage",
    "S3FileStorage",
    "StoredObject",
    "attach_file",
    "build_image_variants",
    "create_uploaded_file",
    "file_storage",
    "get_file_for_read",
    "list_action_logs",
    "list_notifications",
    "list_status_change_logs",
    "mark_all_notifications_read",
    "mark_notification_read",
    "record_action",
    "record_status_change",
    "replace_attached_file",
    "resolve_variant",
    "scrub_sensitive",
    "scrub_text",
    "unread_count",
]
