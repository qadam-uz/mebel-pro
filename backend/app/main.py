"""FastAPI application factory and entrypoint."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from typing import cast

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.errors import (
    APIError,
    api_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging
from app.core.trace import trace_middleware
from app.docs_site import require_docs_auth
from app.docs_site import routers as docs_routers
from app.modules.platform.api import run_platform_scheduler

# The OpenAPI schema stays under the API prefix; the interactive UIs sit beside
# the docs site at /api-docs and /api-redoc (`/docs` is the docs site). All
# three are HTTP-Basic-guarded with the same credentials as /docs.
OPENAPI_URL = f"{settings.API_V1_PREFIX}/openapi.json"
ExceptionHandler = Callable[[Request, Exception], Response | Awaitable[Response]]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    scheduler_task = asyncio.create_task(run_platform_scheduler(SessionLocal))
    try:
        yield
    finally:
        scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await scheduler_task


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title=settings.PROJECT_NAME,
        debug=settings.DEBUG,
        # The built-in OpenAPI routes are unauthenticated, so disable them and
        # register guarded replacements below; `/docs` is the docs site.
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.middleware("http")(trace_middleware)
    app.add_exception_handler(APIError, cast(ExceptionHandler, api_error_handler))
    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, validation_error_handler),
    )
    app.add_exception_handler(StarletteHTTPException, cast(ExceptionHandler, http_error_handler))
    app.add_exception_handler(Exception, unexpected_error_handler)

    _register_openapi_routes(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    for docs_router in docs_routers:
        app.include_router(docs_router)
    return app


def _register_openapi_routes(app: FastAPI) -> None:
    """Auth-protected OpenAPI schema + Swagger/ReDoc UIs."""
    guarded = [Depends(require_docs_auth)]

    @app.get(OPENAPI_URL, include_in_schema=False, dependencies=guarded)
    async def openapi_schema() -> JSONResponse:
        return JSONResponse(app.openapi())

    @app.get("/api-docs", include_in_schema=False, dependencies=guarded)
    async def swagger_ui() -> HTMLResponse:
        return get_swagger_ui_html(openapi_url=OPENAPI_URL, title=f"{app.title} — API")

    @app.get("/api-redoc", include_in_schema=False, dependencies=guarded)
    async def redoc_ui() -> HTMLResponse:
        return get_redoc_html(openapi_url=OPENAPI_URL, title=f"{app.title} — API")


app = create_app()
