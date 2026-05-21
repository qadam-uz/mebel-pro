"""Application error type, the JSON error envelope, and exception handlers.

Every client-facing failure carries a stable machine ``code`` and the request
``trace_id``. The envelope shape is::

    { "code": "forbidden", "detail": "…", "trace_id": "ab12…" }
"""

import traceback
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.core.trace import current_trace_id

_log = get_logger("errors")


class AppError(Exception):
    """A client-facing error with a machine code and an HTTP status."""

    def __init__(
        self,
        code: str,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status_code = status_code
        self.extra = extra or {}


# --- common constructors (used across modules) -----------------------------


def unauthorized(detail: str = "Authentication required.", code: str = "unauthorized") -> AppError:
    return AppError(code, detail, status.HTTP_401_UNAUTHORIZED)


def forbidden(detail: str = "You do not have access to this.", code: str = "forbidden") -> AppError:
    return AppError(code, detail, status.HTTP_403_FORBIDDEN)


def not_found(detail: str = "Not found.", code: str = "not_found") -> AppError:
    return AppError(code, detail, status.HTTP_404_NOT_FOUND)


def conflict(detail: str, code: str = "conflict") -> AppError:
    return AppError(code, detail, status.HTTP_409_CONFLICT)


def bad_request(detail: str, code: str = "bad_request") -> AppError:
    return AppError(code, detail, status.HTTP_400_BAD_REQUEST)


def _envelope(code: str, detail: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "detail": detail, "trace_id": current_trace_id()}
    if extra:
        body.update(extra)
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.detail, exc.extra),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "validation_error",
                "The request is invalid.",
                {"errors": jsonable_encoder(exc.errors())},
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        """Last-resort 500: record the error in the monitor, return a trace envelope.

        Records via a *fresh* session so the request's rollback doesn't lose it.
        """
        trace_id = current_trace_id()
        await _record_server_error(request, exc, trace_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("internal_error", "An unexpected error occurred."),
        )


async def _record_server_error(request: Request, exc: Exception, trace_id: str) -> None:
    """Best-effort record into the error monitor on its own session/transaction."""
    # Imported lazily to avoid an import cycle (errors → db → … → errors).
    from app.core.db import SessionLocal
    from app.services import errors as error_service

    code = f"{type(exc).__module__}.{type(exc).__name__}"
    context = {
        "method": request.method,
        "path": request.url.path,
        "query": str(request.url.query) or None,
    }
    try:
        async with SessionLocal() as db:
            await error_service.record_error(
                db,
                code=code,
                module=request.url.path.strip("/").split("/")[0] or None,
                message=str(exc) or type(exc).__name__,
                stack="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                context=context,
                trace_id=trace_id,
            )
            await db.commit()
    except Exception:  # never let the monitor mask the original 500
        _log.error("error_monitor.record_failed", trace_id=trace_id, code=code)
