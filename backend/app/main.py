"""FastAPI application factory and entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.trace import TraceMiddleware
from app.docs_site import require_docs_auth
from app.docs_site import routers as docs_routers

# The OpenAPI schema stays under the API prefix; the interactive UIs sit beside
# the docs site at /api-docs and /api-redoc (`/docs` is the docs site). All
# three are HTTP-Basic-guarded with the same credentials as /docs.
OPENAPI_URL = f"{settings.API_V1_PREFIX}/openapi.json"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    from app.services.scheduler import scheduler

    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


def create_app() -> FastAPI:
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

    app.add_middleware(TraceMiddleware)
    register_exception_handlers(app)

    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.BACKEND_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

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
