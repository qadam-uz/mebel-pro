"""Request trace-id propagation.

Every request gets a trace id (taken from an inbound ``X-Trace-ID`` or freshly
minted); it rides a context var so logs, the audit log, and error records can
all stamp it, and it is echoed on every response header and in error bodies
(docs/architecture.md → Audit & traceability).
"""

import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

TRACE_HEADER = "X-Trace-ID"


def current_trace_id() -> str:
    return _trace_id_var.get()


def set_trace_id(value: str) -> None:
    _trace_id_var.set(value)


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


class TraceMiddleware(BaseHTTPMiddleware):
    """Bind a trace id to the request context and echo it on the response."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        trace_id = request.headers.get(TRACE_HEADER) or new_trace_id()
        set_trace_id(trace_id)
        response = await call_next(request)
        response.headers[TRACE_HEADER] = trace_id
        return response
