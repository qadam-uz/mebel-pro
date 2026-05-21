"""structlog configuration — every line carries the request trace id."""

import logging
from typing import Any

import structlog

from app.core.config import settings
from app.core.trace import current_trace_id


def _add_trace_id(
    _: Any, __: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    trace_id = current_trace_id()
    if trace_id:
        event_dict["trace_id"] = trace_id
    return event_dict


def configure_logging() -> None:
    """Idempotently configure structlog for the process."""
    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer()
        if settings.ENV == "dev"
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _add_trace_id,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.DEBUG else logging.INFO
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)
