"""Application settings, loaded from environment / `.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import PostgresDsn, computed_field, model_validator
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

    # --- Client auth: Telegram Login (OAuth) -------------------------------
    # The bot token whose SHA-256 keys the Login-Widget HMAC. Empty in dev means
    # the signature check is skipped (so the client app works without a bot);
    # set a real token in any deploy. The widget needs the bot *username*.
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = ""
    TELEGRAM_OAUTH_MAX_AGE_SECONDS: int = 86400

    # --- Docs site ---------------------------------------------------------
    # English docs — the single source of truth — rendered live at `/docs`
    # (Markdown → HTML, no build step). Defaults to the repo's `docs/`;
    # override in containers via `DOCS_DIR`.
    DOCS_DIR: Path = _BACKEND_ROOT.parent / "docs"

    # Uzbek mirror of `docs/` — a derived, read-only translation rendered live
    # at `/docs-uz`. Defaults to the repo's `docs_uz/`; override via
    # `DOCS_UZ_DIR`. Never a source: generated one-way from `DOCS_DIR`.
    DOCS_UZ_DIR: Path = _BACKEND_ROOT.parent / "docs_uz"

    # HTTP Basic credentials guarding `/docs` *and* the OpenAPI UIs
    # (`/api-docs`, `/api-redoc`, the schema). Change these in any real deploy.
    DOCS_AUTH_USERNAME: str = "docs"
    DOCS_AUTH_PASSWORD: str = "docs"  # noqa: S105 — dev default; override in prod

    # --- Object storage (MinIO) --------------------------------------------
    # The `files` module stores material images, workshop logos, receipts, and
    # cutting PDFs in MinIO. In dev/Compose this is the bundled MinIO container;
    # in prod it's the shared MinIO on the VPS's `infra-net` Docker network.
    # The protocol is S3-compatible, so any boto3-style client works.
    MINIO_ENDPOINT_URL: str = "http://localhost:9000"
    MINIO_REGION: str = "us-east-1"
    MINIO_ACCESS_KEY_ID: str = "mebel"
    MINIO_SECRET_ACCESS_KEY: str = "mebel"  # noqa: S105 — dev default; override in prod
    MINIO_BUCKET: str = "mebel"
    MINIO_USE_SSL: bool = False
    # Hard cap on a single uploaded blob (default 10 MB). Enforced per attach
    # context in the `files` module on top of any context-specific limit.
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024

    # --- Database ----------------------------------------------------------
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "mebel"
    POSTGRES_PASSWORD: str = "mebel"  # noqa: S105 — dev default; override in prod
    POSTGRES_DB: str = "mebel"

    # Override to point tests/CI at an alternate database. When unset it is
    # derived from the POSTGRES_* values above.
    DATABASE_URL: str | None = None

    @model_validator(mode="after")
    def _enforce_prod_safety(self) -> "Settings":
        """Fail-closed: refuse to boot in `prod` with insecure dev defaults.

        Two app-served auth surfaces silently fall back to insecure behaviour
        when left unconfigured, which is fine for local dev but unsafe in prod:

        - An empty ``TELEGRAM_BOT_TOKEN`` makes ``verify_telegram_payload``
          skip the HMAC check, so the client app's sign-in becomes forgeable.
        - The default ``DOCS_AUTH_PASSWORD`` (`docs`) is public knowledge and
          guards `/docs` *and* the OpenAPI UIs/schema.

        Catch both at startup instead of in production.
        """
        if self.ENV != "prod":
            return self
        problems: list[str] = []
        if not self.TELEGRAM_BOT_TOKEN:
            problems.append(
                "TELEGRAM_BOT_TOKEN is empty — client Telegram sign-in would be unverified"
            )
        if self.DOCS_AUTH_PASSWORD == "docs":  # noqa: S105 — comparing against the dev default
            problems.append("DOCS_AUTH_PASSWORD is still the dev default 'docs'")
        if problems:
            raise ValueError("Insecure configuration for ENV=prod: " + "; ".join(problems))
        return self

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
