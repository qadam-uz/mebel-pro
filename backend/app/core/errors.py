"""API error classes and FastAPI exception handlers."""

from __future__ import annotations

import traceback
from collections.abc import Mapping
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from structlog import get_logger

from app.core.db import SessionLocal
from app.core.trace import TRACE_HEADER, get_trace_id
from app.services.errors import record_application_error

logger = get_logger(__name__)


class APIError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_body(code: str, message: str, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "trace_id": get_trace_id(),
    }
    if details is not None:
        body["details"] = details
    return body


def _json_error(
    status_code: int,
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    trace_id: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    response_trace_id = trace_id or get_trace_id()
    body: dict[str, Any] = {"code": code, "message": message, "trace_id": response_trace_id}
    if details is not None:
        body["details"] = details
    response_headers = dict(headers or {})
    response_headers[TRACE_HEADER] = response_trace_id
    return JSONResponse(status_code=status_code, content=body, headers=response_headers)


def _request_trace_id(request: Request) -> str:
    trace_id = getattr(request.state, "trace_id", None)
    return trace_id if isinstance(trace_id, str) else get_trace_id()


def _safe_validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    safe_errors: list[dict[str, Any]] = []
    for error in exc.errors():
        safe = dict(error)
        safe.pop("input", None)
        if isinstance(safe.get("ctx"), dict):
            safe["ctx"] = {
                key: value
                if value is None or isinstance(value, str | int | float | bool)
                else str(value)
                for key, value in safe["ctx"].items()
            }
        safe_errors.append(safe)
    return safe_errors


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return _json_error(
        exc.status_code,
        exc.code,
        exc.message,
        details=exc.details,
        trace_id=_request_trace_id(request),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = {"errors": _safe_validation_errors(exc)}
    return _json_error(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        "Invalid request",
        details=details,
        trace_id=_request_trace_id(request),
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    message = detail if isinstance(detail, str) else "HTTP error"
    code = "not_found" if exc.status_code == status.HTTP_404_NOT_FOUND else "http_error"
    return _json_error(
        exc.status_code,
        code,
        message,
        trace_id=_request_trace_id(request),
        headers=exc.headers,
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = _request_trace_id(request)
    await _record_unexpected_error(request, exc, trace_id=trace_id)
    return _json_error(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "Internal server error",
        trace_id=trace_id,
    )


async def _record_unexpected_error(request: Request, exc: Exception, *, trace_id: str) -> None:
    context = {
        "method": request.method,
        "path": request.url.path,
        "query": request.url.query,
        "client": request.client.host if request.client else None,
        "headers": {
            "user-agent": request.headers.get("user-agent"),
            "authorization": request.headers.get("authorization"),
        },
    }
    stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        async with SessionLocal() as db:
            await record_application_error(
                db,
                code=f"{exc.__class__.__module__}.{exc.__class__.__name__}",
                module="api",
                message=str(exc) or exc.__class__.__name__,
                trace_id=trace_id,
                stack=stack,
                context=context,
            )
            await db.commit()
    except Exception as monitor_exc:
        logger.warning("error_monitor_record_failed", exc_info=monitor_exc, trace_id=trace_id)
