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

    # --- Docs site ---------------------------------------------------------
    # English docs — the single source of truth — rendered live at `/docs`
    # (Markdown → HTML, no build step). Defaults to the repo's `docs/`;
    # override in containers via `DOCS_DIR`.
    DOCS_DIR: Path = _BACKEND_ROOT.parent / "docs"

    # HTTP Basic credentials guarding `/docs` *and* the OpenAPI UIs
    # (`/api-docs`, `/api-redoc`, the schema). Change these in any real deploy.
    DOCS_AUTH_USERNAME: str = "docs"
    DOCS_AUTH_PASSWORD: str = "docs"  # noqa: S105 — dev default; override in prod

    # --- Object storage (MinIO) --------------------------------------------
    # The `files` module stores material images, workshop logos, and receipts in
    # MinIO. Cutting PDFs are generated on demand from immutable cutting results.
    # In dev/Compose this is the bundled MinIO container; in prod it's the shared
    # MinIO on the VPS's `infra-net` Docker network.
    # The protocol is S3-compatible, so any boto3-style client works.
    MINIO_ENDPOINT_URL: str = "http://localhost:9000"
    MINIO_REGION: str = "us-east-1"
    MINIO_ACCESS_KEY_ID: str = "mebel"
    MINIO_SECRET_ACCESS_KEY: str = "mebel-secret"  # noqa: S105 — dev default; override in prod
    MINIO_BUCKET: str = "mebel"
    MINIO_USE_SSL: bool = False

    # Client phone-OTP dev sign-in. Empty means the real Telegram flow is required.
    # A non-empty list is a local/CI bypass and is rejected in production unless
    # the explicit pre-production testing override below is set.
    OTP_DEV_CODES: list[str] = []
    ALLOW_PROD_OTP_DEV_CODES: bool = False
    OTP_RATE_LIMITS_ENABLED: bool = True
    # OTP send budgets (each Telegram Gateway message costs money). Env-tunable
    # so an ongoing abuse incident can be throttled with an env edit + restart.
    # The global daily cap is the hard ceiling on the worst-case Telegram bill.
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_PHONE_SENDS_PER_HOUR: int = 5
    OTP_PHONE_SENDS_PER_DAY: int = 10
    OTP_IP_SENDS_PER_HOUR: int = 30
    OTP_IP_SENDS_PER_DAY: int = 50
    OTP_GLOBAL_SENDS_PER_HOUR: int = 150
    OTP_GLOBAL_SENDS_PER_DAY: int = 1000
    OTP_CODE_PEPPER: str = "{{change-me}}"
    TELEGRAM_GATEWAY_ACCESS_TOKEN: str = "{{change-me}}"  # noqa: S105 - secret placeholder.
    TELEGRAM_GATEWAY_API_BASE_URL: str = "https://gatewayapi.telegram.org"
    TELEGRAM_GATEWAY_TIMEOUT_SECONDS: float = 5.0

    # Only trust X-Forwarded-For when the immediate peer is in one of these
    # CIDRs. Keep prod narrow and add the Caddy peer/network explicitly.
    TRUSTED_PROXY_CIDRS: list[str] = ["127.0.0.1/32", "::1/128"]

    # Password login throttle: failed attempts per client IP in a sliding
    # window (in-memory, process-local — the app runs as a single instance).
    # Complements the per-account lockout, which can't cover logins shared
    # across workshops or guessing rotated across many accounts. Env-tunable
    # so an ongoing incident can be throttled without a deploy.
    LOGIN_IP_THROTTLE_ENABLED: bool = True
    LOGIN_IP_MAX_FAILURES: int = 20
    LOGIN_IP_WINDOW_SECONDS: int = 900

    # Public workshop-link resolve budget per client IP. The 8-character code is
    # unguessable (32^8) but the endpoint is unauthenticated, so a budget is what
    # keeps it from being walked or used as a scraping surface. One landing page
    # costs one lookup, so a shared office IP stays far under this.
    PUBLIC_LINK_THROTTLE_ENABLED: bool = True
    PUBLIC_LINK_LOOKUPS_PER_IP: int = 60
    PUBLIC_LINK_WINDOW_SECONDS: int = 60

    # --- Database ----------------------------------------------------------
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "mebel"
    POSTGRES_PASSWORD: str = "mebel"  # noqa: S105 — dev default; override in prod
    POSTGRES_DB: str = "mebel"

    # Override to point tests/CI at an alternate database. When unset it is
    # derived from the POSTGRES_* values above.
    DATABASE_URL: str | None = None

    # Connection pool. These were SQLAlchemy's defaults (5 + 10 overflow, and a
    # 30 s wait); the wait is the one that mattered — on exhaustion a request
    # blocked for half a minute and then succeeded, which reads as "the app
    # froze" and is invisible in logs. A shorter timeout turns that into a
    # fast, traceable 500. Postgres here is shared infrastructure, so the
    # ceiling (POOL_SIZE + MAX_OVERFLOW) is deliberately modest.
    DB_POOL_SIZE: int = 10
    DB_POOL_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT_SECONDS: int = 10
    # Recycle below any idle-connection reaping by the DB or a network hop, so a
    # dead socket is replaced rather than discovered mid-request.
    DB_POOL_RECYCLE_SECONDS: int = 1800

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

    @model_validator(mode="after")
    def validate_security_defaults(self) -> "Settings":
        using_dev_otp_codes = bool(self.OTP_DEV_CODES)
        if self.ENV == "prod" and using_dev_otp_codes and not self.ALLOW_PROD_OTP_DEV_CODES:
            msg = "OTP_DEV_CODES must be empty in production"
            raise ValueError(msg)
        if (
            self.ENV == "prod"
            and not using_dev_otp_codes
            and self.TELEGRAM_GATEWAY_ACCESS_TOKEN in {"", "{{change-me}}"}
        ):
            msg = "TELEGRAM_GATEWAY_ACCESS_TOKEN must be set in production"
            raise ValueError(msg)
        if (
            self.ENV == "prod"
            and not using_dev_otp_codes
            and self.OTP_CODE_PEPPER in {"", "{{change-me}}"}
        ):
            msg = "OTP_CODE_PEPPER must be set in production"
            raise ValueError(msg)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
