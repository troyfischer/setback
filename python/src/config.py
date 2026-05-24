import enum
from urllib.parse import urlparse

from pydantic_settings import BaseSettings

DEFAULT_SESSION_SECRET = "your-super-secret-key"
DEFAULT_JWT_SECRET = "your-secret-key-change-this-in-production"
DEFAULT_JWT_ALGORITHM = "HS256"
DEFAULT_DATABASE_URL = "sqlite:///database.db"
DEFAULT_REDIS_URL = "redis://localhost:6379"
MIN_PRODUCTION_SECRET_LENGTH = 32
LOCAL_HOSTS = {"localhost", "127.0.0.1"}


class AppEnv(enum.StrEnum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class Settings(BaseSettings):
    app_env: AppEnv = AppEnv.DEV
    enable_dev_auth: bool = False
    auto_create_schema: bool = True
    database_url: str = DEFAULT_DATABASE_URL
    redis_url: str = DEFAULT_REDIS_URL
    session_secret: str = DEFAULT_SESSION_SECRET
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = DEFAULT_JWT_ALGORITHM
    base_url: str = "http://localhost"
    client_origin: str = "http://localhost:8081"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    auth_login_rate_limit: int = 20
    auth_login_rate_window_seconds: int = 300
    auth_callback_rate_limit: int = 20
    auth_callback_rate_window_seconds: int = 300
    auth_refresh_rate_limit: int = 30
    auth_refresh_rate_window_seconds: int = 300
    auth_dev_token_rate_limit: int = 20
    auth_dev_token_rate_window_seconds: int = 300
    game_join_rate_limit: int = 30
    game_join_rate_window_seconds: int = 300
    game_subscribe_token_rate_limit: int = 30
    game_subscribe_token_rate_window_seconds: int = 300
    game_sse_connections_per_game_limit: int = 16
    dev_cors_origin_regex: str = (
        r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?"
    )

    @property
    def dev_auth_enabled(self) -> bool:
        return self.app_env in {AppEnv.DEV, AppEnv.TEST} and self.enable_dev_auth

    @property
    def should_auto_create_schema(self) -> bool:
        return self.app_env in {AppEnv.DEV, AppEnv.TEST} and self.auto_create_schema

    @property
    def cors_allowed_origins(self) -> list[str]:
        if self.app_env == AppEnv.PROD:
            return [self.client_origin]
        return []

    @property
    def cors_origin_regex(self) -> str | None:
        if self.app_env == AppEnv.PROD:
            return None
        return self.dev_cors_origin_regex

    def validate_runtime(self) -> None:
        if self.app_env != AppEnv.PROD:
            # allow loose validation for testing purposes
            return

        msg = "{} cannot be enabled when APP_ENV=prod"
        if self.enable_dev_auth:
            raise RuntimeError(msg.format("ENABLE_DEV_AUTH"))
        if self.auto_create_schema:
            raise RuntimeError(msg.format("AUTO_CREATE_SCHEMA"))

        session_secret = self.session_secret.strip()
        jwt_secret = self.jwt_secret.strip()

        if session_secret == DEFAULT_SESSION_SECRET:
            raise RuntimeError("SESSION_SECRET must be changed when APP_ENV=prod")
        if jwt_secret == DEFAULT_JWT_SECRET:
            raise RuntimeError("JWT_SECRET must be changed when APP_ENV=prod")
        if len(session_secret) < MIN_PRODUCTION_SECRET_LENGTH:
            raise RuntimeError(
                "SESSION_SECRET must be at least 32 characters when APP_ENV=prod"
            )
        if len(jwt_secret) < MIN_PRODUCTION_SECRET_LENGTH:
            raise RuntimeError(
                "JWT_SECRET must be at least 32 characters when APP_ENV=prod"
            )
        if self.database_url == DEFAULT_DATABASE_URL:
            raise RuntimeError("DATABASE_URL must be set when APP_ENV=prod")
        if self.redis_url == DEFAULT_REDIS_URL:
            raise RuntimeError("REDIS_URL must be set when APP_ENV=prod")
        if not self.google_client_id or not self.google_client_secret:
            raise RuntimeError(
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set when APP_ENV=prod"
            )

        self._validate_https_url("BASE_URL", self.base_url)
        self._validate_https_url("CLIENT_ORIGIN", self.client_origin)

    @staticmethod
    def _validate_https_url(name: str, value: str) -> None:
        parsed = urlparse(value.strip())
        if parsed.scheme != "https" or not parsed.hostname:
            raise RuntimeError(f"{name} must be an https URL when APP_ENV=prod")
        if parsed.hostname in LOCAL_HOSTS:
            raise RuntimeError(f"{name} cannot target localhost when APP_ENV=prod")
