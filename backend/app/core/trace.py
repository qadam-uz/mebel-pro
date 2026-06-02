"""Request trace-id context and middleware."""

import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from fastapi import Request, Response

TRACE_HEADER = "X-Trace-ID"
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def get_trace_id() -> str:
    trace_id = _trace_id.get()
    if trace_id is None:
        trace_id = new_trace_id()
        _trace_id.set(trace_id)
    return trace_id


def new_trace_id() -> str:
    return uuid.uuid4().hex


async def trace_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    incoming = request.headers.get(TRACE_HEADER)
    trace_id = incoming.strip() if incoming and len(incoming.strip()) <= 128 else new_trace_id()
    request.state.trace_id = trace_id
    token = _trace_id.set(trace_id)
    try:
        response = await call_next(request)
        response.headers[TRACE_HEADER] = trace_id
        return response
    finally:
        _trace_id.reset(token)
