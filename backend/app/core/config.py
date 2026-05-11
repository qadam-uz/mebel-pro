"""Application settings, loaded from environment / `.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → parents[2] == backend/ ; its parent == repo root.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    # --- General -----------------------------------------------------------
    ENV: Literal["dev", "test", "prod"] = "dev"
    DEBUG: bool = False
    PROJECT_NAME: str = "Mebel Pro"
    API_V1_PREFIX: str = "/api/v1"

    # CORS: comma-separated list of allowed origins.
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # --- Docs site ---------------------------------------------------------
    # Directory rendered live at `/docs` (Markdown → HTML, no build step).
    # Defaults to the repo's `docs/`; override in containers via `DOCS_DIR`.
    DOCS_DIR: Path = _BACKEND_ROOT.parent / "docs"

    # HTTP Basic credentials guarding `/docs` *and* the OpenAPI UIs
    # (`/api-docs`, `/api-redoc`, the schema). Change these in any real deploy.
    DOCS_AUTH_USERNAME: str = "docs"
    DOCS_AUTH_PASSWORD: str = "docs"  # noqa: S105 — dev default; override in prod

    # --- Object storage (MinIO / S3-compatible) ----------------------------
    # The `files` module stores material images, workshop logos, receipts, and
    # cutting PDFs here. In dev/Compose this is the bundled MinIO container; in
    # other environments point it at any S3-compatible endpoint.
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY_ID: str = "mebel"
    S3_SECRET_ACCESS_KEY: str = "mebel"  # noqa: S105 — dev default; override in prod
    S3_BUCKET: str = "mebel"
    S3_USE_SSL: bool = False

    # --- Database ----------------------------------------------------------
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "mebel"
    POSTGRES_PASSWORD: str = "mebel"  # noqa: S105 — dev default; override in prod
    POSTGRES_DB: str = "mebel"

    # Override to point tests/CI at an alternate database. When unset it is
    # derived from the POSTGRES_* values above.
    DATABASE_URL: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
