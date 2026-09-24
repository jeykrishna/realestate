from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "PlotBook"
    APP_ENV: str = "development"
    # No default — startup fails explicitly if not set in .env
    SECRET_KEY: str
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Database — no default to force explicit configuration
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    OTP_TTL_SECONDS: int = 600

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # First-admin bootstrap. Anonymous registration via POST /auth/register is
    # DISABLED unless this is set to a non-empty value AND the caller supplies a
    # matching X-Setup-Token header. Leave blank in normal operation — the first
    # admin is created by seed.py. Prevents anonymous admin self-registration.
    SETUP_TOKEN: str = ""

    # Secret keys required to self-register a privileged account via
    # POST /auth/register. Change these in production.
    ADMIN_SECRET_KEY: str = "ADMIN@2024"
    SUPER_ADMIN_SECRET_KEY: str = "SUPERADMIN@2024"

    # Email (AWS SES)
    EMAIL_FROM: str = "noreply@plotbook.in"
    EMAIL_FROM_NAME: str = "PlotBook"
    AWS_SES_REGION: str = "eu-north-1"

    # SMS (AWS SNS)
    AWS_SNS_REGION: str = "eu-north-1"

    # AWS credentials (shared by SES, SNS, S3)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # AWS S3
    # MEDIA_STORAGE selects where uploads go: "local" (writes to
    # /tmp/plotbook-uploads, served at /static/uploads) or "s3".
    # Flip to "s3" once the bucket + CDN are provisioned.
    MEDIA_STORAGE: str = "local"
    S3_BUCKET_NAME: str = "plotbook-media"
    S3_REGION: str = "eu-north-1"
    # Public base URL for served media. Leave blank to fall back to the
    # S3 virtual-hosted URL; set to your CDN origin once wired up.
    CDN_BASE_URL: str = ""

    # Anthropic (AI layout analysis)
    ANTHROPIC_API_KEY: str = ""

    # Rate limiting
    RATE_LIMIT_PUBLIC: str = "60/minute"
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_OTP: str = "3/15minutes"
    # Global per-IP fallback applied to every route (incl. public reads that
    # have no explicit decorator). Generous so it never trips real users; it
    # exists to blunt scraping / abuse.
    RATE_LIMIT_DEFAULT: str = "240/minute"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
